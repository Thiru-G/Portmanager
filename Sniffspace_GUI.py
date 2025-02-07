import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
import serial
import threading
import os
import time

# Use persistent symlinked names based on udev rules
PORTS = [f"/dev/port{i+1}" for i in range(8)]  # Cabins
FEEDER_PORT = "/dev/feeder_port"  # Dedicated feeder port

BAUD_RATE = 115200  # Ensure it matches your device

class SniffSpaceGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SniffSpace Automation")
        self.root.geometry("1400x700")  # Enlarged window size
        self.root.resizable(True, True)  # Allow resizing

        # Apply Azure theme
        self.style = ttk.Style()
        self.root.tk.call("source", os.path.join(os.path.dirname(__file__), "Azure-ttk-theme/azure.tcl"))
        self.root.tk.call("set_theme", "dark")

        self.text_boxes = {}
        self.barrier_states = {}
        self.barrier_buttons = {}

        # 🟢 Main Frame (Cabins)
        self.main_frame = ttk.Frame(root, padding=10)
        self.main_frame.pack(pady=5, fill="x")

        for i, port in enumerate(PORTS):
            frame = ttk.Frame(self.main_frame, padding=5)
            frame.pack(side="left", padx=5)

            # Cabin Label
            label = ttk.Label(frame, text=f"Cabin {i+1}\n{port}", font=("Arial", 12, "bold"))
            label.pack()

            # Barrier Button
            self.barrier_states[port] = False  # Initially OFF
            barrier_btn = ttk.Button(frame, text="Barrier", width=10,
                                     style="Accent.TButton",
                                     command=lambda p=port: self.toggle_barrier(p))
            barrier_btn.pack(pady=2)
            self.barrier_buttons[port] = barrier_btn

            # Text Box for Received Data
            text_box = scrolledtext.ScrolledText(frame, width=18, height=3, wrap=tk.WORD, font=("Courier", 10))
            text_box.pack(pady=5)
            self.text_boxes[port] = text_box

            # Clear Button
            clear_btn = ttk.Button(frame, text="Clear", width=10,
                                   style="Accent.TButton",
                                   command=lambda p=port: self.clear_text_box(p))
            clear_btn.pack(pady=2)

        # 🟢 Bottom Control Panel
        self.bottom_frame = ttk.Frame(root, padding=10)
        self.bottom_frame.pack(fill="x", pady=10)

        open_barriers_btn = ttk.Button(self.bottom_frame, text="Open All Barriers", width=20,
                                       style="Accent.TButton",
                                       command=self.open_all_barriers)
        open_barriers_btn.pack(side="left", padx=10)

        close_barriers_btn = ttk.Button(self.bottom_frame, text="Close All Barriers", width=20,
                                        style="Danger.TButton",
                                        command=self.close_all_barriers)
        close_barriers_btn.pack(side="left", padx=10)

        global_feeder_btn = ttk.Button(self.bottom_frame, text="Activate All Feeders", width=20,
                                       style="Accent.TButton",
                                       command=lambda: self.activate_all("activate_feeder"))
        global_feeder_btn.pack(side="left", padx=10)

        # 🟢 Check Ports Button
        check_ports_btn = ttk.Button(self.bottom_frame, text="Check Ports", width=20,
                                     style="Accent.TButton",
                                     command=self.check_ports)
        check_ports_btn.pack(side="left", padx=10)

        # Live Log Display (For Check Ports Output)
        self.log_text = scrolledtext.ScrolledText(self.bottom_frame, width=80, height=10, wrap=tk.WORD, font=("Courier", 12))
        self.log_text.pack(side="left", padx=10)

        # Clear Log Button
        clear_log_btn = ttk.Button(self.bottom_frame, text="Clear Log", width=15,
                                   style="Accent.TButton",
                                   command=self.clear_log)
        clear_log_btn.pack(side="left", padx=10)

        # 🟢 Feeder Section (Dedicated Port)
        self.feeder_frame = ttk.Frame(root, padding=10)
        self.feeder_frame.pack(fill="x", pady=10)

        feeder_label = ttk.Label(self.feeder_frame, text=f"Feeder Control ({FEEDER_PORT})", font=("Arial", 14, "bold"))
        feeder_label.pack()

        feeder_button = ttk.Button(self.feeder_frame, text="Activate Feeder", width=20,
                                   style="Accent.TButton",
                                   command=self.activate_feeder)
        feeder_button.pack(pady=5)

        self.feeder_text = scrolledtext.ScrolledText(self.feeder_frame, width=50, height=3, wrap=tk.WORD, font=("Courier", 10))
        self.feeder_text.pack()

        # Start the background thread to listen for serial data
        self.running = True
        self.serial_threads = []
        self.start_serial_listeners()

    def clear_log(self):
        """ Clears the main log text box """
        self.log_text.delete(1.0, tk.END)

    def clear_text_box(self, port):
        """ Clears the text box for a specific port """
        if port in self.text_boxes:
            self.text_boxes[port].delete(1.0, tk.END)

    def toggle_barrier(self, port):
        """ Toggles barrier activation and updates button color/text """
        if self.barrier_states[port]:  # If ON, deactivate
            command = "deactivate_gate"
            self.barrier_states[port] = False
            self.barrier_buttons[port].config(text="Barrier", style="Accent.TButton")
        else:  # If OFF, activate
            command = "activate_gate"
            self.barrier_states[port] = True
            self.barrier_buttons[port].config(text="Barrier (ON)", style="Danger.TButton")

        self.send_command(port, command)

    def open_all_barriers(self):
        """ Opens all barriers """
        for port in PORTS:
            self.send_command(port, "activate_gate")
            self.barrier_states[port] = True
            self.barrier_buttons[port].config(text="Barrier (ON)", style="Danger.TButton")

    def close_all_barriers(self):
        """ Closes all barriers """
        for port in PORTS:
            self.send_command(port, "deactivate_gate")
            self.barrier_states[port] = False
            self.barrier_buttons[port].config(text="Barrier", style="Accent.TButton")

    def activate_feeder(self):
        """ Sends feeder activation command to the dedicated feeder port """
        self.send_command(FEEDER_PORT, "activate_feeder", feeder=True)

    def activate_all(self, command):
        """ Sends a command to all ports """
        for port in PORTS:
            self.send_command(port, command)

    def check_ports(self):
        """ Sends 'check' command to all ports and logs responses in the main log box """
        self.log_text.insert(tk.END, "[INFO] Checking all ports...\n")
        self.log_text.yview(tk.END)
        # For the check command, force output to main log (ignore feeder flag)
        for port in PORTS + [FEEDER_PORT]:
            self.send_command(port, "check", feeder=False)

    def send_command(self, port, command, feeder=False):
        """
        Sends a command to the given serial port and logs the response.
        For the 'check' command, the response is always logged in the main log box.
        """
        try:
            if not os.path.exists(port):
                target_log = self.log_text
                target_log.insert(tk.END, f"[ERROR] Port {port} not found.\n")
                target_log.yview(tk.END)
                return

            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                ser.write((command + "\n").encode())

                # Read response from the serial device
                response = ser.readline().decode().strip()

                # For the check command, always log to main log
                if command.strip().lower() == "check":
                    target_log = self.log_text
                else:
                    target_log = self.feeder_text if feeder else self.log_text

                target_log.insert(tk.END, f"[{port}] {command} → Response: {response}\n")
                target_log.yview(tk.END)

        except serial.SerialException as e:
            self.log_text.insert(tk.END, f"[ERROR] Serial Error on {port}: {e}\n")
            self.log_text.yview(tk.END)

    def start_serial_listeners(self):
        """ Starts background threads to listen for incoming serial data """
        for port in PORTS + [FEEDER_PORT]:
            thread = threading.Thread(target=self.listen_serial, args=(port,), daemon=True)
            self.serial_threads.append(thread)
            thread.start()

    def listen_serial(self, port):
        """ Listens for incoming serial data using a timing buffer and updates the GUI """
        buffer = ""  # Temporary buffer to accumulate data
        last_time = None
        TIMEOUT = 0.2  # 200 ms timeout for flushing the buffer

        try:
            with serial.Serial(port, BAUD_RATE, timeout=0.1) as ser:
                while self.running:
                    if ser.in_waiting > 0:
                        char = ser.read().decode(errors="ignore")
                        buffer += char
                        last_time = time.time()
                        if char == "\n":
                            data = buffer.strip()
                            buffer = ""
                            self.root.after(0, self.update_text_box, port, data)
                    else:
                        # If no new data and the buffer is not empty, check for timeout
                        if buffer and last_time and (time.time() - last_time) > TIMEOUT:
                            data = buffer.strip()
                            buffer = ""
                            self.root.after(0, self.update_text_box, port, data)
        except serial.SerialException as e:
            self.root.after(0, lambda: self.log_text.insert(tk.END, f"[ERROR] Serial Error on {port}: {e}\n"))
            self.root.after(0, self.log_text.yview, tk.END)

    def update_text_box(self, port, data):
        """ Updates the appropriate text box with incoming serial data """
        target = self.feeder_text if port == FEEDER_PORT else self.text_boxes.get(port)
        if target:
            target.insert(tk.END, f"[{port}] {data}\n")
            target.yview(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = SniffSpaceGUI(root)
    root.mainloop()
