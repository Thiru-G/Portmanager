import tkinter as tk
from tkinter import simpledialog, messagebox
from tkinter import ttk
import serial.tools.list_ports
import subprocess
import os

UDEV_RULE_PATH = '/etc/udev/rules.d/99-esp32.rules'  # Path to udev rules file

# Function to list all available serial ports and check if they have symbolic names and serial numbers
def get_serial_ports():
    ports = list(serial.tools.list_ports.comports())
    available_ports = []
    
    for port in ports:
        serial_number = port.serial_number if port.serial_number else "N/A"
        # Only add ports with valid devices and serial numbers
        if serial_number != "N/A" and port.device:
            symbolic_name = get_symbolic_name_by_serial(serial_number)
            if symbolic_name:
                available_ports.append(f"Symbolic: {symbolic_name} | {port.device} - {port.description} | Serial: {serial_number} | ")
            else:
                available_ports.append(f" (No symbolic name) {port.device} - {port.description} (Serial: {serial_number}) ")
    
    return available_ports

# Function to get symbolic name of a port by serial number from the udev rules
def get_symbolic_name_by_serial(serial_number):
    if os.path.exists(UDEV_RULE_PATH):
        with open(UDEV_RULE_PATH, 'r') as f:
            rules = f.readlines()
        
        # Loop through all the udev rules
        for rule in rules:
            # Check if the serial number is in the rule and the rule contains SYMLINK
            if serial_number in rule and 'SYMLINK+=' in rule:
                # Extract the symbolic name between the quotes after SYMLINK+=
                symbolic_name = rule.split('SYMLINK+="')[1].split('"')[0]
                return symbolic_name
    return None

# Function to onboard a selected port with a custom symbolic name
def onboard_port(selected_port):
    port_device = selected_port.split(" - ")[0]
    serial_number = selected_port.split("Serial: ")[1].split(")")[0]  # Extract serial number
    custom_name = simpledialog.askstring("Onboard Port", f"Enter the custom name for the port with serial {serial_number}:")
    
    if serial_number and custom_name:
        rule = f'SUBSYSTEM=="tty", ATTRS{{serial}}=="{serial_number}", SYMLINK+="{custom_name}"\n'
        
        # Append the new rule to the file
        with open(UDEV_RULE_PATH, 'a') as f:
            f.write(rule)
        
        reload_udev_rules()
        messagebox.showinfo("Success", f"Port with serial {serial_number} onboarded with name: {custom_name}")
        refresh_ports()

# Function to replace a port's serial number in an existing symbolic name
def replace_serial_in_symbolic_name():
    selected_port = dropdown.get()
    serial_number = selected_port.split("Serial: ")[1].split(")")[0]  # Extract serial number
    existing_symbolic_name = get_symbolic_name_by_serial(serial_number)
    
    if not existing_symbolic_name:
        messagebox.showerror("Error", f"No symbolic name found for the port with serial {serial_number}.")
        return
    
    new_port = simpledialog.askstring("Replace Serial", f"Enter the new port's serial number to map to '{existing_symbolic_name}':")
    
    if new_port:
        replaced = False
        if os.path.exists(UDEV_RULE_PATH):
            with open(UDEV_RULE_PATH, 'r') as f:
                rules = f.readlines()
            
            # Replace the old serial number with the new one in the matching rule
            with open(UDEV_RULE_PATH, 'w') as f:
                for rule in rules:
                    if existing_symbolic_name in rule and 'SYMLINK+=' in rule:
                        rule = rule.split('ATTRS{serial}')[0] + f'ATTRS{{serial}}=="{new_port}", SYMLINK+="{existing_symbolic_name}"\n'
                        replaced = True
                    f.write(rule)
        
        if replaced:
            reload_udev_rules()
            messagebox.showinfo("Success", f"Symbolic name '{existing_symbolic_name}' now maps to serial {new_port}.")
            refresh_ports()
        else:
            messagebox.showerror("Error", f"Failed to replace the serial for '{existing_symbolic_name}'.")

# Function to rename a symbolic name for an existing serial number
def rename_symbolic_name():
    selected_port = dropdown.get()
    serial_number = selected_port.split("Serial: ")[1].split(")")[0]  # Extract serial number
    existing_symbolic_name = get_symbolic_name_by_serial(serial_number)
    
    if not existing_symbolic_name:
        messagebox.showerror("Error", f"No symbolic name found for the port with serial {serial_number}.")
        return
    
    new_symbolic_name = simpledialog.askstring("Rename Symbolic Name", f"Enter the new symbolic name for serial {serial_number}:")
    
    if new_symbolic_name and existing_symbolic_name:
        renamed = False
        if os.path.exists(UDEV_RULE_PATH):
            with open(UDEV_RULE_PATH, 'r') as f:
                rules = f.readlines()
            
            # Rename the symbolic name in the matching rule
            with open(UDEV_RULE_PATH, 'w') as f:
                for rule in rules:
                    if existing_symbolic_name in rule and 'SYMLINK+=' in rule:
                        rule = rule.replace(f'SYMLINK+="{existing_symbolic_name}"', f'SYMLINK+="{new_symbolic_name}"')
                        renamed = True
                    f.write(rule)
        
        if renamed:
            reload_udev_rules()
            messagebox.showinfo("Success", f"Symbolic name '{existing_symbolic_name}' renamed to '{new_symbolic_name}'.")
            refresh_ports()
        else:
            messagebox.showerror("Error", f"Failed to rename '{existing_symbolic_name}'.")

# Function to delete a symbolic name rule
def delete_symbolic_name():
    selected_port = dropdown.get()
    serial_number = selected_port.split("Serial: ")[1].split(")")[0]  # Extract serial number
    symbolic_name = get_symbolic_name_by_serial(serial_number)
    
    if not symbolic_name:
        messagebox.showerror("Error", f"No symbolic name found for the port with serial {serial_number}.")
        return
    
    deleted = False
    if os.path.exists(UDEV_RULE_PATH):
        with open(UDEV_RULE_PATH, 'r') as f:
            rules = f.readlines()
        
        # Remove the matching rule from the file
        with open(UDEV_RULE_PATH, 'w') as f:
            for rule in rules:
                if symbolic_name not in rule:
                    f.write(rule)
                else:
                    deleted = True
    
    if deleted:
        reload_udev_rules()
        messagebox.showinfo("Success", f"Symbolic name '{symbolic_name}' has been deleted.")
        refresh_ports()
    else:
        messagebox.showerror("Error", f"Symbolic name '{symbolic_name}' not found.")

# Function to reload udev rules
def reload_udev_rules():
    try:
        subprocess.run(['sudo', 'udevadm', 'control', '--reload-rules'], check=True)
        subprocess.run(['sudo', 'udevadm', 'trigger'], check=True)
        messagebox.showinfo("Success", "Udev rules reloaded successfully!")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to reload udev rules: {e}")

# Function to refresh the list of ports
def refresh_ports():
    available_ports = get_serial_ports()
    dropdown['values'] = available_ports
    if available_ports:
        dropdown.current(0)
    else:
        dropdown.set("No available ports found")

# GUI Setup
root = tk.Tk()
root.title("Dognosis Port Manager")

# Set window size
root.geometry("600x450")

# Apply the Azure theme for ttk widgets
root.tk.call("source", "/home/sniffspace/Downloads/Thiru_s scripts/Portmanager/Azure-ttk-theme/azure.tcl")
root.tk.call("set_theme", "light")  # Options are "light" or "dark"

# Frame for branding and app title
branding_frame = ttk.Frame(root)
branding_frame.pack(fill=tk.X, pady=10)

title_label = ttk.Label(branding_frame, text="Dognosis Serial Port Manager", font=("Helvetica", 18, "bold"), anchor="center")
title_label.pack()

# Main frame for the app content
frame = ttk.Frame(root)
frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)

# Label for dropdown
ttk.Label(frame, text="Select a Serial Port:", font=("Helvetica", 12)).pack(pady=5)

# Dropdown for available serial ports
available_ports = get_serial_ports()
selected_port = tk.StringVar()

dropdown = ttk.Combobox(frame, textvariable=selected_port, values=available_ports, state="readonly", font=("Helvetica", 10))
dropdown.pack(pady=10, fill=tk.X)
if available_ports:
    dropdown.current(0)
else:
    dropdown.set("No available ports found")

# Buttons for actions
button_frame = ttk.Frame(frame)
button_frame.pack(pady=20)

ttk.Button(button_frame, text="Onboard Selected Port", command=lambda: onboard_port(selected_port.get()), style="Accent.TButton", width=30).pack(pady=5)
ttk.Button(button_frame, text="Replace Serial in Symbolic Name", command=replace_serial_in_symbolic_name, style="Accent.TButton", width=30).pack(pady=5)
ttk.Button(button_frame, text="Rename Symbolic Name", command=rename_symbolic_name, style="Accent.TButton", width=30).pack(pady=5)
ttk.Button(button_frame, text="Delete Symbolic Name", command=delete_symbolic_name, style="Accent.TButton", width=30).pack(pady=5)
ttk.Button(button_frame, text="Refresh Port List", command=refresh_ports, style="Accent.TButton", width=30).pack(pady=5)

# Add padding and styling
for child in frame.winfo_children():
    child.pack_configure(padx=10, pady=5)

root.mainloop()