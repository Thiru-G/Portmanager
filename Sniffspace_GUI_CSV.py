import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
import serial
import threading
import os
import time
import csv

# Use persistent symlinked names based on udev rules
PORTS = [f"/dev/port{i+1}" for i in range(8)]  # Cabins
FEEDER_PORT = "/dev/feeder_port"  # Dedicated feeder port
BAUD_RATE = 115200  # Ensure it matches your device
LOG_CSV_FILE = "serial_log.csv"  # CSV file to store all received serial data

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

        self.barrier_states = {}
        self.barrier_buttons = {}

        # Ensure the CSV file exists
        self.init_csv()

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

        global_feeder_btn = ttk.Button(self.bottom_frame, text="Activate Feeder", width=20,
                                       style="Accent.TButton",
                                       command=self.activate_feeder)
        global_feeder_btn.pack(side="left", padx=10)

        # 🟢 Check Ports Button
        check_ports_btn = ttk.Button(self.bottom_frame, text="Check Ports", width=20,
                                     style="Accent.TButton",
                                     command=self.check_ports)
        check_ports_btn.pack(side="left", padx=10)

        # Live Log Display (Central Log Box)
        self.log_text = scrolledtext.ScrolledText(self.bottom_frame, width=100, height=15, wrap=tk.WORD, font=("Courier", 12))
        self.log_text.pack(pady=10)

        # Clear Log Button
        clear_log_btn = ttk.Button(self.bottom_frame, text="Clear Log", width=15,
                                   style="Accent.TButton",
                                   command=self.clear_log)
        clear_log_btn.pack(side="left", padx=10)

        # Start the background thread to listen for serial data
        self.running = True
        self.serial_threads = []
        self.start_serial_listeners()

    def init_csv(self):
        """Ensure the CSV file exists with a header."""
        if not os.path.exists(LOG_CSV_FILE):
            with open(LOG_CSV_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Port", "Data"])

    def log_serial_data(self, port, data):
        """ Logs all received serial data into a CSV file with a timestamp. """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_CSV_FILE, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, port, data])

        self.log_text.insert(tk.END, f"[{timestamp}] {port}: {data}\n")
        self.log_text.yview(tk.END)
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

    def clear_log(self):
        """ Clears the main log text box """
        self.log_text.delete(1.0, tk.END)

    def check_ports(self):
        """ Sends 'check' command to all ports and logs responses in the main log box """
        self.log_text.insert(tk.END, "[INFO] Checking all ports...\n")
        self.log_text.yview(tk.END)
        for port in PORTS + [FEEDER_PORT]:
            self.send_command(port, "check", feeder=False)

    def send_command(self, port, command, feeder=False):
        """ Sends command to serial port and logs response. """
        try:
            if not os.path.exists(port):
                self.log_text.insert(tk.END, f"[ERROR] Port {port} not found.\n")
                self.log_text.yview(tk.END)
                return

            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                ser.write((command + "\n").encode())

                # Read response from the serial device
                response = ser.readline().decode().strip()

                self.log_serial_data(port, response)  # Log all received data

        except serial.SerialException as e:
            self.log_text.insert(tk.END, f"[ERROR] Serial Error on {port}: {e}\n")
            self.log_text.yview(tk.END)

    def start_serial_listeners(self):
        """ Starts background threads to listen for incoming serial data """
        for port in PORTS + [FEEDER_PORT]:
            thread = threading.Thread(target=self.listen_serial, args=(port,), daemon=True)
            self.serial_threads.append(thread)
            thread.start()  
    def activate_feeder(self):
        """ Sends feeder activation command to the dedicated feeder port """
        self.send_command(FEEDER_PORT, "activate_feeder", feeder=True)
    def listen_serial(self, port):
        """ Listens for incoming serial data and logs only full messages. """
        buffer = ""  # Accumulates data until a full message is received

        try:
            with serial.Serial(port, BAUD_RATE, timeout=1) as ser:
                while self.running:
                    if ser.in_waiting > 0:
                        char = ser.read().decode(errors="ignore")  # Read one character at a time
                        buffer += char  # Append character to buffer

                        if char == "\n":  # Only process when newline is received
                            data = buffer.strip()  # Remove spaces/newlines
                            buffer = ""  # Reset buffer for next message

                            # Log the complete response
                            self.log_serial_data(port, data)
        except serial.SerialException as err:
            self.root.after(0, lambda err=err: self.log_text.insert(tk.END, f"[ERROR] Serial Error on {port}: {err}\n"))
            self.root.after(0, self.log_text.yview, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = SniffSpaceGUI(root)
    root.mainloop()