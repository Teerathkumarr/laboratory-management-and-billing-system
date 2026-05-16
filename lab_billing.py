import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import datetime
import os
import csv
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
import hashlib

class LoginWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("THAR PATHOLOGY LABORATORY - Login")
        self.root.geometry("400x300")
        self.root.configure(bg='#2c3e50')
        
        # Center the window
        self.root.eval('tk::PlaceWindow . center')
        
        self.create_widgets()
        self.create_default_admin()
    
    def create_default_admin(self):
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        # Create users table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        ''')
        
        # Create default admin if not exists
        default_password = hashlib.sha256("admin123".encode()).hexdigest()
        try:
            cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', 
                          ('admin', default_password, 'admin'))
        except:
            pass
        
        conn.commit()
        conn.close()
    
    def create_widgets(self):
        # Main frame
        main_frame = tk.Frame(self.root, bg='#2c3e50', padx=20, pady=20)
        main_frame.pack(expand=True, fill='both')
        
        # Title
        title_label = tk.Label(main_frame, text="THAR PATHOLOGY LABORATORY", 
                              font=('Arial', 18, 'bold'), fg='white', bg='#2c3e50')
        title_label.pack(pady=(0, 30))
        
        # Login frame
        login_frame = tk.Frame(main_frame, bg='#34495e', padx=20, pady=20, relief='raised', bd=2)
        login_frame.pack(expand=True, fill='both')
        
        # Username
        tk.Label(login_frame, text="Username:", font=('Arial', 12), 
                fg='white', bg='#34495e').grid(row=0, column=0, sticky='w', pady=10)
        self.username_entry = tk.Entry(login_frame, font=('Arial', 12), width=20)
        self.username_entry.grid(row=0, column=1, pady=10, padx=10)
        
        # Password
        tk.Label(login_frame, text="Password:", font=('Arial', 12), 
                fg='white', bg='#34495e').grid(row=1, column=0, sticky='w', pady=10)
        self.password_entry = tk.Entry(login_frame, font=('Arial', 12), 
                                     show='*', width=20)
        self.password_entry.grid(row=1, column=1, pady=10, padx=10)
        
        # Login button
        login_btn = tk.Button(login_frame, text="LOGIN", font=('Arial', 12, 'bold'),
                             bg='#27ae60', fg='white', width=15, command=self.login)
        login_btn.grid(row=2, column=0, columnspan=2, pady=20)
        
        # Bind Enter key to login
        self.root.bind('<Return>', lambda event: self.login())
        
        # Set focus to username entry
        self.username_entry.focus()
    
    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                      (username, hashed_password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            self.root.destroy()
            main_root = tk.Tk()
            app = LaboratoryBillingSystem(main_root, username, user[3])  # Pass role
            main_root.mainloop()
        else:
            messagebox.showerror("Error", "Invalid username or password")
            self.password_entry.delete(0, tk.END)
            self.username_entry.focus()

class LaboratoryBillingSystem:
    def __init__(self, root, username, role):
        self.root = root
        self.username = username
        self.role = role  # Store user role
        self.root.title(f"THAR PATHOLOGY LABORATORY - Welcome {username}")
        self.root.geometry("1200x700")
        self.root.configure(bg='#ecf0f1')
        
        # Store current bill data for printing
        self.current_bill_data = None
        
        # Initialize database
        self.init_database()
        
        # Create main frame
        self.create_main_frame()
        
        # Load reports
        self.load_reports()
        
    def init_database(self):
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        # Create patients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                contact TEXT,
                gender TEXT,
                doctor_name TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create reports table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL,
                expected_time TEXT DEFAULT '24 hours'
            )
        ''')
        
        # Create bills table with discount_amount column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                bill_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL,
                discount_amount REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                remaining_amount REAL DEFAULT 0,
                bill_number TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')
        
        # Create bill_items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bill_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id INTEGER,
                report_id INTEGER,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (bill_id) REFERENCES bills (id),
                FOREIGN KEY (report_id) REFERENCES reports (id)
            )
        ''')
        
        # Add discount column if not exists (for existing databases)
        try:
            cursor.execute("ALTER TABLE bills ADD COLUMN discount_amount REAL DEFAULT 0")
        except:
            pass  # Column already exists
        
        # Add bill_number column if not exists
        try:
            cursor.execute("ALTER TABLE bills ADD COLUMN bill_number TEXT")
        except:
            pass  # Column already exists
        
        # Add some sample reports if none exist
        cursor.execute('SELECT COUNT(*) FROM reports')
        if cursor.fetchone()[0] == 0:
            sample_reports = [
                ('Complete Blood Count', 500.00, '4 hours'),
                ('Blood Glucose Test', 300.00, '2 hours'),
                ('Lipid Profile', 800.00, '24 hours'),
                ('Liver Function Test', 1200.00, '24 hours'),
                ('Thyroid Test', 900.00, '24 hours'),
                ('Urine Analysis', 250.00, '2 hours'),
                ('X-Ray Chest', 600.00, '1 hour'),
                ('ECG', 400.00, '30 minutes')
            ]
            cursor.executemany('INSERT INTO reports (name, price, expected_time) VALUES (?, ?, ?)', sample_reports)
        
        conn.commit()
        conn.close()
    
    def generate_sample_id(self):
        """Generate sample ID with monthly reset"""
        current_month = datetime.datetime.now().strftime("%Y%m")
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        # Get the last sample ID for this month
        cursor.execute('''
            SELECT bill_number FROM bills 
            WHERE bill_number LIKE ? 
            ORDER BY id DESC LIMIT 1
        ''', (f'THAR-{current_month}-%',))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            last_number = int(result[0].split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"THAR-{current_month}-{new_number:04d}"
    
    def create_main_frame(self):
        # Create notebook for tabs
        style = ttk.Style()
        style.configure('TNotebook.Tab', padding=[20, 5], font=('Arial', 10))
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=10, pady=10)
        
        # Create frames for each tab
        self.billing_frame = ttk.Frame(self.notebook)
        self.patients_frame = ttk.Frame(self.notebook)
        self.reports_frame = ttk.Frame(self.notebook)
        self.revenue_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(self.billing_frame, text="Billing")
        self.notebook.add(self.patients_frame, text="Patients")
        self.notebook.add(self.reports_frame, text="Reports Management")
        self.notebook.add(self.revenue_frame, text="Revenue Reports")
        self.notebook.add(self.settings_frame, text="Settings")
        
        # Initialize each tab
        self.create_billing_tab()
        self.create_patients_tab()
        self.create_reports_tab()
        self.create_revenue_tab()
        self.create_settings_tab()
    
    def create_billing_tab(self):
        # Main frame
        main_frame = ttk.Frame(self.billing_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left frame - Patient Info
        left_frame = ttk.LabelFrame(main_frame, text="Patient Information", padding=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Patient form
        ttk.Label(left_frame, text="Name:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        self.name_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.name_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Age:*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.age_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.age_entry.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Mobile Number:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5)
        self.contact_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.contact_entry.grid(row=2, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Gender:*", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
        self.gender_combo = ttk.Combobox(left_frame, values=["Male", "Female", "Other"], 
                                       width=28, font=('Arial', 10), state='readonly')
        self.gender_combo.grid(row=3, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Doctor:", font=('Arial', 10)).grid(row=4, column=0, sticky='w', pady=5)
        self.doctor_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.doctor_entry.grid(row=4, column=1, pady=5, padx=5)
        
        # Payment Information
        ttk.Label(left_frame, text="Payment Information", font=('Arial', 11, 'bold')).grid(row=5, column=0, columnspan=2, pady=(20, 10), sticky='w')
        
        ttk.Label(left_frame, text="Paid Amount:*", font=('Arial', 10)).grid(row=6, column=0, sticky='w', pady=5)
        self.paid_amount_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.paid_amount_entry.grid(row=6, column=1, pady=5, padx=5)
        self.paid_amount_entry.insert(0, "0")
        self.paid_amount_entry.bind('<KeyRelease>', lambda e: self.calculate_total())
        
        # Discount Field
        ttk.Label(left_frame, text="Discount (₹):", font=('Arial', 10)).grid(row=7, column=0, sticky='w', pady=5)
        self.discount_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.discount_entry.grid(row=7, column=1, pady=5, padx=5)
        self.discount_entry.insert(0, "0")
        self.discount_entry.bind('<KeyRelease>', lambda e: self.calculate_total())
        
        # Date and time
        ttk.Label(left_frame, text="Date & Time:", font=('Arial', 10)).grid(row=8, column=0, sticky='w', pady=5)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.datetime_label = ttk.Label(left_frame, text=current_time, font=('Arial', 10))
        self.datetime_label.grid(row=8, column=1, sticky='w', pady=5, padx=5)
        
        # Right frame - Billing
        right_frame = ttk.LabelFrame(main_frame, text="Billing", padding=10)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Reports search frame
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill='x', pady=5)
        
        ttk.Label(search_frame, text="Search Reports:", font=('Arial', 10)).pack(side='left', padx=5)
        self.billing_search_entry = ttk.Entry(search_frame, width=20, font=('Arial', 10))
        self.billing_search_entry.pack(side='left', padx=5)
        self.billing_search_entry.bind('<KeyRelease>', self.search_billing_reports)
        
        ttk.Button(search_frame, text="Clear", command=self.clear_billing_search).pack(side='left', padx=5)
        
        # Reports selection
        ttk.Label(right_frame, text="Available Reports:", font=('Arial', 10)).pack(anchor='w', pady=(10, 0))
        self.reports_listbox = tk.Listbox(right_frame, selectmode='multiple', height=8, 
                                         font=('Arial', 10))
        self.reports_listbox.pack(fill='both', expand=True, pady=5)
        
        # Add scrollbar to listbox
        listbox_scrollbar = ttk.Scrollbar(self.reports_listbox)
        listbox_scrollbar.pack(side='right', fill='y')
        self.reports_listbox.config(yscrollcommand=listbox_scrollbar.set)
        listbox_scrollbar.config(command=self.reports_listbox.yview)
        
        # Add selected reports button
        ttk.Button(right_frame, text="Add Selected Reports", 
                  command=self.add_selected_reports).pack(pady=5)
        
        # Selected reports frame
        selected_frame = ttk.LabelFrame(right_frame, text="Selected Reports", padding=5)
        selected_frame.pack(fill='both', expand=True, pady=5)
        
        # Treeview for selected reports
        columns = ('Report', 'Price', 'Quantity', 'Expected Time')
        self.selected_tree = ttk.Treeview(selected_frame, columns=columns, show='headings', height=6)
        
        column_widths = {'Report': 150, 'Price': 80, 'Quantity': 60, 'Expected Time': 100}
        for col in columns:
            self.selected_tree.heading(col, text=col)
            self.selected_tree.column(col, width=column_widths[col])
        
        self.selected_tree.pack(fill='both', expand=True)
        
        # Remove selected button
        ttk.Button(selected_frame, text="Remove Selected", 
                  command=self.remove_selected_report).pack(pady=5)
        
        # Total amount with discount
        total_frame = ttk.Frame(right_frame)
        total_frame.pack(fill='x', pady=10)
        
        # Subtotal
        ttk.Label(total_frame, text="Subtotal:", font=('Arial', 11, 'bold')).grid(row=0, column=0, sticky='w')
        self.subtotal_label = ttk.Label(total_frame, text="₹0.00", font=('Arial', 11))
        self.subtotal_label.grid(row=0, column=1, padx=10)
        
        # Discount
        ttk.Label(total_frame, text="Discount:", font=('Arial', 11, 'bold')).grid(row=1, column=0, sticky='w')
        self.discount_label = ttk.Label(total_frame, text="₹0.00", font=('Arial', 11), foreground='orange')
        self.discount_label.grid(row=1, column=1, padx=10)
        
        # Total Amount
        ttk.Label(total_frame, text="Total Amount:", font=('Arial', 12, 'bold')).grid(row=2, column=0, sticky='w', pady=(5,0))
        self.total_label = ttk.Label(total_frame, text="₹0.00", font=('Arial', 12, 'bold'), foreground='green')
        self.total_label.grid(row=2, column=1, padx=10, pady=(5,0))
        
        # Paid and Remaining
        ttk.Label(total_frame, text="Paid:", font=('Arial', 11, 'bold')).grid(row=3, column=0, sticky='w')
        self.paid_label = ttk.Label(total_frame, text="₹0.00", font=('Arial', 11), foreground='blue')
        self.paid_label.grid(row=3, column=1, padx=10)
        
        ttk.Label(total_frame, text="Remaining:", font=('Arial', 11, 'bold')).grid(row=4, column=0, sticky='w')
        self.remaining_label = ttk.Label(total_frame, text="₹0.00", font=('Arial', 11), foreground='red')
        self.remaining_label.grid(row=4, column=1, padx=10)
        
        # Action buttons
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill='x', pady=10)
        
        ttk.Button(button_frame, text="Generate Bill", 
                  command=self.generate_bill).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Print Patient Receipt", 
                  command=lambda: self.print_receipt('patient')).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Print Lab Copy", 
                  command=lambda: self.print_receipt('lab')).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear Form", 
                  command=self.clear_billing_form).pack(side='left', padx=5)
    
    def create_patients_tab(self):
        main_frame = ttk.Frame(self.patients_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Search frame
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill='x', pady=10)
        
        ttk.Label(search_frame, text="Search:", font=('Arial', 10)).pack(side='left', padx=5)
        self.patient_search_entry = ttk.Entry(search_frame, width=30, font=('Arial', 10))
        self.patient_search_entry.pack(side='left', padx=5)
        self.patient_search_entry.bind('<KeyRelease>', self.search_patients)
        
        ttk.Button(search_frame, text="Search", 
                  command=self.search_patients).pack(side='left', padx=5)
        ttk.Button(search_frame, text="Show All", 
                  command=self.load_patients).pack(side='left', padx=5)
        
        # Patients treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)
        
        columns = ('ID', 'Name', 'Age', 'Mobile Number', 'Gender', 'Doctor', 'Date Added')
        self.patients_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        column_widths = {'ID': 50, 'Name': 120, 'Age': 50, 'Mobile Number': 100, 'Gender': 70, 'Doctor': 120, 'Date Added': 120}
        for col in columns:
            self.patients_tree.heading(col, text=col)
            self.patients_tree.column(col, width=column_widths[col])
        
        # Add scrollbar
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.patients_tree.yview)
        self.patients_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.patients_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=10)
        
        ttk.Button(button_frame, text="Edit Patient", 
                  command=self.edit_patient).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Delete Patient", 
                  command=self.delete_patient).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Refresh", 
                  command=self.load_patients).pack(side='left', padx=5)
        
        # Load patients
        self.load_patients()
    
    def create_reports_tab(self):
        main_frame = ttk.Frame(self.reports_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left frame - Add/Edit reports
        left_frame = ttk.LabelFrame(main_frame, text="Report Management", padding=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        ttk.Label(left_frame, text="Report Name:*", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        self.report_name_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.report_name_entry.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Price (₹):*", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
        self.report_price_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.report_price_entry.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(left_frame, text="Expected Time:*", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
        self.report_time_entry = ttk.Entry(left_frame, width=30, font=('Arial', 10))
        self.report_time_entry.grid(row=2, column=1, pady=5, padx=5)
        self.report_time_entry.insert(0, "24 hours")
        
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Add Report", 
                  command=self.add_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Update Report", 
                  command=self.update_report).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear Form", 
                  command=self.clear_report_form).pack(side='left', padx=5)
        
        # Right frame - Reports list
        right_frame = ttk.LabelFrame(main_frame, text="Available Reports", padding=10)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Search frame
        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill='x', pady=5)
        
        ttk.Label(search_frame, text="Search:", font=('Arial', 10)).pack(side='left', padx=5)
        self.report_search_entry = ttk.Entry(search_frame, width=20, font=('Arial', 10))
        self.report_search_entry.pack(side='left', padx=5)
        self.report_search_entry.bind('<KeyRelease>', self.search_reports)
        
        # Reports treeview frame
        tree_frame = ttk.Frame(right_frame)
        tree_frame.pack(fill='both', expand=True, pady=10)
        
        columns = ('ID', 'Name', 'Price', 'Expected Time')
        self.reports_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        column_widths = {'ID': 50, 'Name': 150, 'Price': 80, 'Expected Time': 100}
        for col in columns:
            self.reports_tree.heading(col, text=col)
            self.reports_tree.column(col, width=column_widths[col])
        
        # Add scrollbar
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.reports_tree.yview)
        self.reports_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.reports_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # Action buttons for reports
        report_button_frame = ttk.Frame(right_frame)
        report_button_frame.pack(fill='x', pady=5)
        
        ttk.Button(report_button_frame, text="Delete Report", 
                  command=self.delete_report).pack(side='left', padx=5)
        ttk.Button(report_button_frame, text="Refresh", 
                  command=self.load_reports_tree).pack(side='left', padx=5)
        
        # Bind double click to edit
        self.reports_tree.bind('<Double-1>', self.on_report_double_click)
        
        # Load reports
        self.load_reports_tree()
    
    def create_revenue_tab(self):
        main_frame = ttk.Frame(self.revenue_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=10)
        
        # Create a sub-frame for filter elements
        filter_content = ttk.Frame(filter_frame)
        filter_content.pack(fill='x', padx=10, pady=5)
        
        # Date filters
        ttk.Label(filter_content, text="From Date:", font=('Arial', 10)).pack(side='left', padx=5)
        self.from_date = ttk.Entry(filter_content, width=12, font=('Arial', 10))
        self.from_date.pack(side='left', padx=5)
        self.from_date.insert(0, datetime.datetime.now().strftime("%Y-%m-01"))
        
        ttk.Label(filter_content, text="To Date:", font=('Arial', 10)).pack(side='left', padx=5)
        self.to_date = ttk.Entry(filter_content, width=12, font=('Arial', 10))
        self.to_date.pack(side='left', padx=5)
        self.to_date.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        
        # Time filters
        ttk.Label(filter_content, text="From Time:", font=('Arial', 10)).pack(side='left', padx=5)
        self.from_time = ttk.Combobox(filter_content, 
                                    values=["00:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"], 
                                    width=8, font=('Arial', 10), state='readonly')
        self.from_time.pack(side='left', padx=5)
        self.from_time.set("00:00")
        
        ttk.Label(filter_content, text="To Time:", font=('Arial', 10)).pack(side='left', padx=5)
        self.to_time = ttk.Combobox(filter_content, 
                                  values=["23:59", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"], 
                                  width=8, font=('Arial', 10), state='readonly')
        self.to_time.pack(side='left', padx=5)
        self.to_time.set("23:59")
        
        ttk.Button(filter_content, text="Apply Filter", 
                  command=self.load_revenue_data).pack(side='left', padx=10)
        
        # Export buttons in separate frame
        export_frame = ttk.Frame(filter_content)
        export_frame.pack(side='right', padx=10)
        
        ttk.Button(export_frame, text="Export to CSV", 
                  command=self.export_revenue_csv).pack(side='left', padx=5)
        ttk.Button(export_frame, text="Export to PDF", 
                  command=self.export_revenue_pdf).pack(side='left', padx=5)
        
        # Revenue treeview frame
        tree_frame = ttk.LabelFrame(main_frame, text="Revenue Data", padding=10)
        tree_frame.pack(fill='both', expand=True, pady=10)
        
        columns = ('Bill ID', 'Patient Name', 'Date', 'Total Amount', 'Discount', 'Paid', 'Remaining')
        self.revenue_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        column_widths = {'Bill ID': 80, 'Patient Name': 150, 'Date': 120, 
                        'Total Amount': 100, 'Discount': 80, 'Paid': 80, 'Remaining': 80}
        for col in columns:
            self.revenue_tree.heading(col, text=col)
            self.revenue_tree.column(col, width=column_widths[col])
        
        tree_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.revenue_tree.yview)
        self.revenue_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        self.revenue_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding=10)
        summary_frame.pack(fill='x', pady=10)
        
        ttk.Label(summary_frame, text="Total Revenue:", font=('Arial', 11, 'bold')).pack(side='left', padx=10)
        self.total_revenue_label = ttk.Label(summary_frame, text="₹0.00", 
                                           font=('Arial', 11, 'bold'), foreground='green')
        self.total_revenue_label.pack(side='left', padx=5)
        
        ttk.Label(summary_frame, text="Total Bills:", font=('Arial', 11, 'bold')).pack(side='left', padx=10)
        self.total_bills_label = ttk.Label(summary_frame, text="0", 
                                         font=('Arial', 11, 'bold'), foreground='blue')
        self.total_bills_label.pack(side='left', padx=5)
        
        ttk.Label(summary_frame, text="Total Collected:", font=('Arial', 11, 'bold')).pack(side='left', padx=10)
        self.total_collected_label = ttk.Label(summary_frame, text="₹0.00", 
                                            font=('Arial', 11, 'bold'), foreground='orange')
        self.total_collected_label.pack(side='left', padx=5)
        
        # Load initial data
        self.load_revenue_data()
    
    def create_settings_tab(self):
        main_frame = ttk.Frame(self.settings_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Only show settings to admin users
        if self.role != 'admin':
            ttk.Label(main_frame, text="Access Denied", font=('Arial', 16, 'bold')).pack(expand=True)
            ttk.Label(main_frame, text="Only administrators can access settings", font=('Arial', 12)).pack(pady=10)
            return
        
        # User management frame
        user_frame = ttk.LabelFrame(main_frame, text="User Management", padding=10)
        user_frame.pack(fill='x', pady=10)
        
        ttk.Label(user_frame, text="New Username:*", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5, padx=10)
        self.new_username = ttk.Entry(user_frame, width=20, font=('Arial', 10))
        self.new_username.grid(row=0, column=1, pady=5, padx=10)
        
        ttk.Label(user_frame, text="New Password:*", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5, padx=10)
        self.new_password = ttk.Entry(user_frame, width=20, font=('Arial', 10), show='*')
        self.new_password.grid(row=1, column=1, pady=5, padx=10)
        
        ttk.Label(user_frame, text="Role:*", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5, padx=10)
        self.role_combo = ttk.Combobox(user_frame, values=["user", "admin"], width=17, font=('Arial', 10), state='readonly')
        self.role_combo.grid(row=2, column=1, pady=5, padx=10)
        self.role_combo.set("user")
        
        ttk.Button(user_frame, text="Add User", 
                  command=self.add_user).grid(row=3, column=0, columnspan=2, pady=10)
        
        # Database frame
        db_frame = ttk.LabelFrame(main_frame, text="Database Management", padding=10)
        db_frame.pack(fill='x', pady=10)
        
        button_frame = ttk.Frame(db_frame)
        button_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(button_frame, text="Backup Database", 
                  command=self.backup_database).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset Database", 
                  command=self.reset_database).pack(side='left', padx=5)
        
        # System info frame
        info_frame = ttk.LabelFrame(main_frame, text="System Information", padding=10)
        info_frame.pack(fill='x', pady=10)
        
        info_content = ttk.Frame(info_frame)
        info_content.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(info_content, text=f"Logged in as: {self.username} ({self.role})", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_content, text=f"Database: lab_billing.db", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_content, text=f"Version: 2.0", font=('Arial', 10)).pack(anchor='w')
        ttk.Label(info_content, text=f"Contact: 03452869527 / +92 345 3879556", font=('Arial', 10)).pack(anchor='w')
    
    def calculate_total(self):
        """Calculate total amount with discount"""
        subtotal = 0.0
        for item in self.selected_tree.get_children():
            values = self.selected_tree.item(item)['values']
            price = float(values[1].replace('₹', ''))
            quantity = int(values[2])
            subtotal += price * quantity
        
        try:
            discount = float(self.discount_entry.get() or 0)
            if discount < 0:
                discount = 0
                self.discount_entry.delete(0, tk.END)
                self.discount_entry.insert(0, "0")
        except ValueError:
            discount = 0
            self.discount_entry.delete(0, tk.END)
            self.discount_entry.insert(0, "0")
        
        try:
            paid_amount = float(self.paid_amount_entry.get() or 0)
            if paid_amount < 0:
                paid_amount = 0
                self.paid_amount_entry.delete(0, tk.END)
                self.paid_amount_entry.insert(0, "0")
        except ValueError:
            paid_amount = 0
            self.paid_amount_entry.delete(0, tk.END)
            self.paid_amount_entry.insert(0, "0")
        
        total_amount = subtotal - discount
        remaining = total_amount - paid_amount
        
        # Update all labels
        self.subtotal_label.config(text=f"₹{subtotal:.2f}")
        self.discount_label.config(text=f"₹{discount:.2f}")
        self.total_label.config(text=f"₹{total_amount:.2f}")
        self.paid_label.config(text=f"₹{paid_amount:.2f}")
        self.remaining_label.config(text=f"₹{remaining:.2f}")
    
    def search_billing_reports(self, event=None):
        search_term = self.billing_search_entry.get().strip().lower()
        self.load_reports(search_term)
    
    def clear_billing_search(self):
        self.billing_search_entry.delete(0, tk.END)
        self.load_reports()
    
    def load_reports(self, search_term=None):
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute('SELECT name, price, expected_time FROM reports WHERE LOWER(name) LIKE ? ORDER BY name', 
                          (f'%{search_term}%',))
        else:
            cursor.execute('SELECT name, price, expected_time FROM reports ORDER BY name')
            
        reports = cursor.fetchall()
        conn.close()
        
        self.reports_listbox.delete(0, tk.END)
        for report in reports:
            self.reports_listbox.insert(tk.END, f"{report[0]} - ₹{report[1]:.2f} - {report[2]}")
    
    def add_selected_reports(self):
        selected_indices = self.reports_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Warning", "Please select at least one report")
            return
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        for index in selected_indices:
            report_text = self.reports_listbox.get(index)
            report_name = report_text.split(' - ₹')[0]
            
            cursor.execute('SELECT id, name, price, expected_time FROM reports WHERE name = ?', (report_name,))
            report = cursor.fetchone()
            
            if report:
                # Check if already in tree
                existing = False
                for item in self.selected_tree.get_children():
                    if self.selected_tree.item(item)['values'][0] == report[1]:
                        existing = True
                        break
                
                if not existing:
                    self.selected_tree.insert('', 'end', values=(report[1], f"₹{report[2]:.2f}", 1, report[3]))
        
        conn.close()
        self.calculate_total()
    
    def remove_selected_report(self):
        selected_item = self.selected_tree.selection()
        if selected_item:
            self.selected_tree.delete(selected_item)
            self.calculate_total()
    
    def validate_patient_data(self):
        name = self.name_entry.get().strip()
        age = self.age_entry.get().strip()
        contact = self.contact_entry.get().strip()
        gender = self.gender_combo.get().strip()
        paid_amount = self.paid_amount_entry.get().strip()
        discount = self.discount_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Please enter patient name")
            self.name_entry.focus()
            return False
        
        if not age.isdigit() or int(age) <= 0 or int(age) > 150:
            messagebox.showerror("Error", "Please enter a valid age (1-150)")
            self.age_entry.focus()
            return False
        
        # Updated mobile validation for 11 digits
        if contact and (not contact.isdigit() or len(contact) != 11):
            messagebox.showerror("Error", "Please enter a valid 11-digit mobile number")
            self.contact_entry.focus()
            return False
        
        if not gender:
            messagebox.showerror("Error", "Please select gender")
            self.gender_combo.focus()
            return False
        
        if not paid_amount.replace('.', '').isdigit() or float(paid_amount) < 0:
            messagebox.showerror("Error", "Please enter a valid paid amount")
            self.paid_amount_entry.focus()
            return False
        
        if not discount.replace('.', '').isdigit() or float(discount) < 0:
            messagebox.showerror("Error", "Please enter a valid discount amount")
            self.discount_entry.focus()
            return False
        
        if not self.selected_tree.get_children():
            messagebox.showerror("Error", "Please add at least one report")
            return False
        
        return True
    
    def generate_bill(self):
        if not self.validate_patient_data():
            return
        
        try:
            conn = sqlite3.connect('lab_billing.db')
            cursor = conn.cursor()
            
            # Add patient
            cursor.execute('''
                INSERT INTO patients (name, age, contact, gender, doctor_name) 
                VALUES (?, ?, ?, ?, ?)
            ''', (self.name_entry.get().strip(), 
                  int(self.age_entry.get().strip()), 
                  self.contact_entry.get().strip(), 
                  self.gender_combo.get().strip(),
                  self.doctor_entry.get().strip()))
            
            patient_id = cursor.lastrowid
            
            # Calculate amounts
            subtotal = 0.0
            for item in self.selected_tree.get_children():
                values = self.selected_tree.item(item)['values']
                price = float(values[1].replace('₹', ''))
                quantity = int(values[2])
                subtotal += price * quantity
            
            discount = float(self.discount_entry.get() or 0)
            total_amount = subtotal - discount
            paid_amount = float(self.paid_amount_entry.get() or 0)
            remaining_amount = total_amount - paid_amount
            
            # Generate sample ID
            sample_id = self.generate_sample_id()
            
            # Create bill with discount and sample ID
            cursor.execute('''
                INSERT INTO bills (patient_id, total_amount, discount_amount, paid_amount, remaining_amount, bill_number) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (patient_id, total_amount, discount, paid_amount, remaining_amount, sample_id))
            
            bill_id = cursor.lastrowid
            
            # Add bill items
            for item in self.selected_tree.get_children():
                values = self.selected_tree.item(item)['values']
                report_name = values[0]
                
                cursor.execute('SELECT id FROM reports WHERE name = ?', (report_name,))
                report = cursor.fetchone()
                
                if report:
                    cursor.execute('''
                        INSERT INTO bill_items (bill_id, report_id, quantity) 
                        VALUES (?, ?, ?)
                    ''', (bill_id, report[0], int(values[2])))
            
            conn.commit()
            conn.close()
            
            # Store current bill data for printing
            self.current_bill_data = {
                'sample_id': sample_id,
                'subtotal': subtotal,
                'discount': discount,
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'remaining': remaining_amount
            }
            
            messagebox.showinfo("Success", 
                              f"Bill generated successfully!\n"
                              f"Sample ID: {sample_id}\n"
                              f"Subtotal: ₹{subtotal:.2f}\n"
                              f"Discount: ₹{discount:.2f}\n"
                              f"Total Amount: ₹{total_amount:.2f}\n\n"
                              f"You can now print receipts using the Print buttons.")
            
            # DON'T clear the form here - let user print first
            # self.clear_billing_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate bill: {str(e)}")
    
    def print_receipt(self, receipt_type='patient'):
        # Check if bill has been generated first
        if not self.current_bill_data:
            if not self.validate_patient_data():
                return
            # If no bill generated but form is valid, generate bill first
            self.generate_bill()
            return
        
        if receipt_type == 'patient':
            filename = f"patient_receipt_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            self.generate_patient_receipt(filename)
        else:
            filename = f"lab_copy_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            self.generate_lab_copy_receipt(filename)
        
        try:
            # "Print" the file (opens print dialog on Windows)
            os.startfile(filename, "print")
            messagebox.showinfo("Success", f"{receipt_type.capitalize()} receipt sent to printer!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to print receipt: {str(e)}")
    
    def generate_patient_receipt(self, filename):
        """Generate professional patient receipt"""
        page_width = 80 * mm
        page_height = 180 * mm
        doc = SimpleDocTemplate(filename, pagesize=(page_width, page_height), 
                               topMargin=5*mm, bottomMargin=5*mm, 
                               leftMargin=3*mm, rightMargin=3*mm)
        elements = []
        styles = getSampleStyleSheet()
        
        # Professional styles
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.black,
            alignment=1,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        )
        
        subheader_style = ParagraphStyle(
            'Subheader',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            alignment=1,
            spaceAfter=4,
            fontName='Helvetica'
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2,
            fontName='Helvetica'
        )
        
        bold_style = ParagraphStyle(
            'Bold',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        )
        
        # Header
        header = Paragraph("THAR PATHOLOGY LABORATORY", header_style)
        elements.append(header)
        
        # Sample Information - Changed from Bill No to Sample ID
        sample_id = self.current_bill_data['sample_id']
        sample_info = [
            [f"Sample ID: {sample_id}"],
            [f"Date: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"]
        ]
        
        sample_table = Table(sample_info, colWidths=[74*mm])
        sample_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(sample_table)
        elements.append(Spacer(1, 8))
        
        # Patient info - Well aligned
        patient_data = [
            ["Patient Name:", self.name_entry.get().strip()],
            ["Age/Gender:", f"{self.age_entry.get().strip()}/{self.gender_combo.get().strip()}"],
            ["Contact No:", self.contact_entry.get().strip() or "N/A"],
            ["Doctor:", self.doctor_entry.get().strip() or "N/A"]
        ]
        
        patient_table = Table(patient_data, colWidths=[25*mm, 49*mm])
        patient_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(patient_table)
        elements.append(Spacer(1, 8))
        
        # Tests Table - Professional alignment
        tests_data = [['Test', 'Price', 'Qty', 'Amount']]
        subtotal = 0.0
        
        for item in self.selected_tree.get_children():
            values = self.selected_tree.item(item)['values']
            price = float(values[1].replace('₹', ''))
            quantity = int(values[2])
            amount = price * quantity
            subtotal += amount
            
            # Smart text wrapping for test names
            test_name = values[0]
            if len(test_name) > 22:
                test_name = test_name[:22] + "..."
                
            tests_data.append([test_name, f"₹{price:.0f}", str(quantity), f"₹{amount:.0f}"])
        
        tests_table = Table(tests_data, colWidths=[35*mm, 12*mm, 8*mm, 15*mm])
        tests_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 7),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        elements.append(tests_table)
        elements.append(Spacer(1, 8))
        
        # Calculate totals
        discount = self.current_bill_data['discount']
        total_amount = self.current_bill_data['total_amount']
        paid_amount = self.current_bill_data['paid_amount']
        remaining = self.current_bill_data['remaining']
        
        # Summary - Professional formatting
        summary_data = [
            ["Subtotal:", f"₹{subtotal:.2f}"],
            ["Discount:", f"₹{discount:.2f}"],
            ["Total Amount:", f"₹{total_amount:.2f}"],
            ["Paid Amount:", f"₹{paid_amount:.2f}"],
            ["Balance Due:", f"₹{remaining:.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[25*mm, 25*mm])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 2), (-1, 2), 1, colors.black),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
            ('FONT', (0, -1), (-1, -1), 'Helvetica-Bold', 9),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 12))
        
        # Footer with contact information and instructions
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.black,
            alignment=1,
            spaceBefore=6
        )
        
        thank_you = Paragraph("Thank you for choosing THAR PATHOLOGY LABORATORY", footer_style)
        elements.append(thank_you)
        
        bring_copy = Paragraph("Please bring this copy when collecting reports", footer_style)
        elements.append(bring_copy)
        
        contact_info = Paragraph("Contact: 03452869527 / +92 345 3879556", footer_style)
        elements.append(contact_info)
        
        doc.build(elements)
    
    def generate_lab_copy_receipt(self, filename):
        """Generate professional lab copy receipt with same Sample ID"""
        page_width = 80 * mm
        page_height = 150 * mm
        doc = SimpleDocTemplate(filename, pagesize=(page_width, page_height), 
                               topMargin=5*mm, bottomMargin=5*mm, 
                               leftMargin=3*mm, rightMargin=3*mm)
        elements = []
        styles = getSampleStyleSheet()
        
        # Professional styles
        header_style = ParagraphStyle(
            'Header',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.black,
            alignment=1,
            spaceAfter=4,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2,
            fontName='Helvetica'
        )
        
        bold_style = ParagraphStyle(
            'Bold',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.black,
            alignment=0,
            spaceAfter=2,
            fontName='Helvetica-Bold'
        )
        
        # Header - Changed from "STAFF COPY" to "LAB COPY"
        header = Paragraph("THAR PATHOLOGY LABORATORY - LAB COPY", header_style)
        elements.append(header)
        
        # Sample ID and Date - Same Sample ID as patient receipt
        sample_id = self.current_bill_data['sample_id']
        sample_info = [
            [f"Sample ID: {sample_id}"],
            [f"Date: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}"]
        ]
        
        sample_table = Table(sample_info, colWidths=[74*mm])
        sample_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(sample_table)
        elements.append(Spacer(1, 6))
        
        # Patient Information - Including contact
        patient_data = [
            ["Patient Name:", self.name_entry.get().strip()],
            ["Contact No:", self.contact_entry.get().strip() or "N/A"],
            ["Age/Gender:", f"{self.age_entry.get().strip()}/{self.gender_combo.get().strip()}"],
            ["Doctor:", self.doctor_entry.get().strip() or "N/A"]
        ]
        
        patient_table = Table(patient_data, colWidths=[25*mm, 49*mm])
        patient_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica', 8),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(patient_table)
        elements.append(Spacer(1, 8))
        
        # Tests to Collect - Professional layout
        elements.append(Paragraph("TESTS TO BE COLLECTED:", bold_style))
        elements.append(Spacer(1, 4))
        
        tests_data = [['Test', 'Time']]
        
        for item in self.selected_tree.get_children():
            values = self.selected_tree.item(item)['values']
            
            # Smart text wrapping
            test_name = values[0]
            if len(test_name) > 35:
                test_name = test_name[:35] + "..."
                
            tests_data.append([test_name, values[3]])
        
        tests_table = Table(tests_data, colWidths=[55*mm, 19*mm])
        tests_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
            ('FONT', (0, 1), (-1, -1), 'Helvetica', 7),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        elements.append(tests_table)
        elements.append(Spacer(1, 8))
        
        # Calculate totals for lab copy
        subtotal = self.current_bill_data['subtotal']
        discount = self.current_bill_data['discount']
        total_amount = self.current_bill_data['total_amount']
        
        # Financial Summary for Lab Copy - Added subtotal and discount
        summary_data = [
            ["Subtotal:", f"₹{subtotal:.2f}"],
            ["Discount:", f"₹{discount:.2f}"],
            ["Total Amount:", f"₹{total_amount:.2f}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[30*mm, 25*mm])
        summary_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), 'Helvetica-Bold', 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('LINEABOVE', (0, 0), (-1, 0), 1, colors.black),
            ('LINEABOVE', (0, -1), (-1, -1), 1, colors.black),
        ]))
        elements.append(summary_table)
        
        # Footer with instructions
        elements.append(Spacer(1, 10))
        
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.black,
            alignment=1,
            spaceBefore=4
        )
        
        instructions = Paragraph("Handle with care - Verify patient details before sample collection", footer_style)
        elements.append(instructions)
        
        contact_info = Paragraph("Contact: 03452869527 / +92 345 3879556", footer_style)
        elements.append(contact_info)
        
        doc.build(elements)
    
    def clear_billing_form(self):
        self.name_entry.delete(0, tk.END)
        self.age_entry.delete(0, tk.END)
        self.contact_entry.delete(0, tk.END)
        self.gender_combo.set('')
        self.doctor_entry.delete(0, tk.END)
        self.paid_amount_entry.delete(0, tk.END)
        self.paid_amount_entry.insert(0, "0")
        self.discount_entry.delete(0, tk.END)
        self.discount_entry.insert(0, "0")
        self.selected_tree.delete(*self.selected_tree.get_children())
        self.calculate_total()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.datetime_label.config(text=current_time)
        self.billing_search_entry.delete(0, tk.END)
        self.load_reports()
        # Clear current bill data
        self.current_bill_data = None
    
    def load_patients(self):
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, age, contact, gender, doctor_name, created_date 
            FROM patients ORDER BY created_date DESC
        ''')
        patients = cursor.fetchall()
        conn.close()
        
        self.patients_tree.delete(*self.patients_tree.get_children())
        for patient in patients:
            # Format date for display
            formatted_date = patient[6]
            if formatted_date:
                try:
                    formatted_date = datetime.datetime.strptime(patient[6], '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y %H:%M')
                except:
                    pass
            self.patients_tree.insert('', 'end', values=(
                patient[0], patient[1], patient[2], patient[3], patient[4], patient[5], formatted_date
            ))
    
    def search_patients(self, event=None):
        search_term = self.patient_search_entry.get().strip()
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute('''
                SELECT id, name, age, contact, gender, doctor_name, created_date 
                FROM patients 
                WHERE name LIKE ? OR contact LIKE ? OR doctor_name LIKE ?
                ORDER BY created_date DESC
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute('''
                SELECT id, name, age, contact, gender, doctor_name, created_date 
                FROM patients ORDER BY created_date DESC
            ''')
        
        patients = cursor.fetchall()
        conn.close()
        
        self.patients_tree.delete(*self.patients_tree.get_children())
        for patient in patients:
            # Format date for display
            formatted_date = patient[6]
            if formatted_date:
                try:
                    formatted_date = datetime.datetime.strptime(patient[6], '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y %H:%M')
                except:
                    pass
            self.patients_tree.insert('', 'end', values=(
                patient[0], patient[1], patient[2], patient[3], patient[4], patient[5], formatted_date
            ))
    
    def edit_patient(self):
        selected_item = self.patients_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a patient to edit")
            return
        
        patient_data = self.patients_tree.item(selected_item[0])['values']
        
        # Create edit dialog
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Patient")
        edit_window.geometry("300x250")
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        ttk.Label(edit_window, text="Name:*", font=('Arial', 10)).grid(row=0, column=0, sticky='w', pady=5, padx=10)
        name_entry = ttk.Entry(edit_window, width=20, font=('Arial', 10))
        name_entry.grid(row=0, column=1, pady=5, padx=10)
        name_entry.insert(0, patient_data[1])
        
        ttk.Label(edit_window, text="Age:*", font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=5, padx=10)
        age_entry = ttk.Entry(edit_window, width=20, font=('Arial', 10))
        age_entry.grid(row=1, column=1, pady=5, padx=10)
        age_entry.insert(0, patient_data[2])
        
        ttk.Label(edit_window, text="Mobile:", font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=5, padx=10)
        contact_entry = ttk.Entry(edit_window, width=20, font=('Arial', 10))
        contact_entry.grid(row=2, column=1, pady=5, padx=10)
        contact_entry.insert(0, patient_data[3])
        
        ttk.Label(edit_window, text="Gender:*", font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=5, padx=10)
        gender_combo = ttk.Combobox(edit_window, values=["Male", "Female", "Other"], width=17, font=('Arial', 10))
        gender_combo.grid(row=3, column=1, pady=5, padx=10)
        gender_combo.set(patient_data[4])
        
        ttk.Label(edit_window, text="Doctor:", font=('Arial', 10)).grid(row=4, column=0, sticky='w', pady=5, padx=10)
        doctor_entry = ttk.Entry(edit_window, width=20, font=('Arial', 10))
        doctor_entry.grid(row=4, column=1, pady=5, padx=10)
        doctor_entry.insert(0, patient_data[5])
        
        def save_changes():
            if not name_entry.get().strip():
                messagebox.showerror("Error", "Name is required")
                return
            
            conn = sqlite3.connect('lab_billing.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE patients 
                SET name=?, age=?, contact=?, gender=?, doctor_name=?
                WHERE id=?
            ''', (name_entry.get().strip(), 
                  int(age_entry.get().strip()), 
                  contact_entry.get().strip(), 
                  gender_combo.get().strip(),
                  doctor_entry.get().strip(),
                  patient_data[0]))
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", "Patient updated successfully")
            edit_window.destroy()
            self.load_patients()
        
        ttk.Button(edit_window, text="Save", command=save_changes).grid(row=5, column=0, columnspan=2, pady=10)
        edit_window.mainloop()
    
    def delete_patient(self):
        selected_item = self.patients_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a patient to delete")
            return
        
        patient_data = self.patients_tree.item(selected_item[0])['values']
        
        if messagebox.askyesno("Confirm", f"Delete patient {patient_data[1]}?"):
            conn = sqlite3.connect('lab_billing.db')
            cursor = conn.cursor()
            
            # Check if patient has bills
            cursor.execute('SELECT COUNT(*) FROM bills WHERE patient_id = ?', (patient_data[0],))
            bill_count = cursor.fetchone()[0]
            
            if bill_count > 0:
                messagebox.showerror("Error", "Cannot delete patient with existing bills")
            else:
                cursor.execute('DELETE FROM patients WHERE id = ?', (patient_data[0],))
                conn.commit()
                messagebox.showinfo("Success", "Patient deleted successfully")
                self.load_patients()
            
            conn.close()
    
    def load_reports_tree(self):
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, price, expected_time FROM reports ORDER BY name')
        reports = cursor.fetchall()
        conn.close()
        
        self.reports_tree.delete(*self.reports_tree.get_children())
        for report in reports:
            self.reports_tree.insert('', 'end', values=report)
    
    def search_reports(self, event=None):
        search_term = self.report_search_entry.get().strip()
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute('SELECT id, name, price, expected_time FROM reports WHERE name LIKE ? ORDER BY name', 
                          (f'%{search_term}%',))
        else:
            cursor.execute('SELECT id, name, price, expected_time FROM reports ORDER BY name')
        
        reports = cursor.fetchall()
        conn.close()
        
        self.reports_tree.delete(*self.reports_tree.get_children())
        for report in reports:
            self.reports_tree.insert('', 'end', values=report)
    
    def on_report_double_click(self, event):
        selected_item = self.reports_tree.selection()
        if selected_item:
            report_data = self.reports_tree.item(selected_item[0])['values']
            self.report_name_entry.delete(0, tk.END)
            self.report_name_entry.insert(0, report_data[1])
            self.report_price_entry.delete(0, tk.END)
            self.report_price_entry.insert(0, str(report_data[2]))
            self.report_time_entry.delete(0, tk.END)
            self.report_time_entry.insert(0, report_data[3])
    
    def add_report(self):
        name = self.report_name_entry.get().strip()
        price = self.report_price_entry.get().strip()
        expected_time = self.report_time_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Please enter report name")
            self.report_name_entry.focus()
            return
        
        try:
            price_val = float(price)
            if price_val <= 0:
                raise ValueError("Price must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid price")
            self.report_price_entry.focus()
            return
        
        if not expected_time:
            messagebox.showerror("Error", "Please enter expected time")
            self.report_time_entry.focus()
            return
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO reports (name, price, expected_time) VALUES (?, ?, ?)', 
                          (name, price_val, expected_time))
            conn.commit()
            messagebox.showinfo("Success", "Report added successfully")
            self.clear_report_form()
            self.load_reports_tree()
            self.load_reports()  # Refresh billing tab
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Report with this name already exists")
        finally:
            conn.close()
    
    def update_report(self):
        selected_item = self.reports_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a report to update")
            return
        
        report_data = self.reports_tree.item(selected_item[0])['values']
        name = self.report_name_entry.get().strip()
        price = self.report_price_entry.get().strip()
        expected_time = self.report_time_entry.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Please enter report name")
            return
        
        try:
            price_val = float(price)
            if price_val <= 0:
                raise ValueError("Price must be positive")
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid price")
            return
        
        if not expected_time:
            messagebox.showerror("Error", "Please enter expected time")
            return
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('UPDATE reports SET name=?, price=?, expected_time=? WHERE id=?', 
                          (name, price_val, expected_time, report_data[0]))
            conn.commit()
            messagebox.showinfo("Success", "Report updated successfully")
            self.clear_report_form()
            self.load_reports_tree()
            self.load_reports()  # Refresh billing tab
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Report with this name already exists")
        finally:
            conn.close()
    
    def delete_report(self):
        selected_item = self.reports_tree.selection()
        if not selected_item:
            messagebox.showwarning("Warning", "Please select a report to delete")
            return
        
        report_data = self.reports_tree.item(selected_item[0])['values']
        
        if messagebox.askyesno("Confirm", f"Delete report {report_data[1]}?"):
            conn = sqlite3.connect('lab_billing.db')
            cursor = conn.cursor()
            
            # Check if report is used in any bills
            cursor.execute('SELECT COUNT(*) FROM bill_items WHERE report_id = ?', (report_data[0],))
            usage_count = cursor.fetchone()[0]
            
            if usage_count > 0:
                messagebox.showerror("Error", "Cannot delete report that is used in existing bills")
            else:
                cursor.execute('DELETE FROM reports WHERE id = ?', (report_data[0],))
                conn.commit()
                messagebox.showinfo("Success", "Report deleted successfully")
                self.load_reports_tree()
                self.load_reports()  # Refresh billing tab
            
            conn.close()
    
    def clear_report_form(self):
        self.report_name_entry.delete(0, tk.END)
        self.report_price_entry.delete(0, tk.END)
        self.report_time_entry.delete(0, tk.END)
        self.report_time_entry.insert(0, "24 hours")
    
    def load_revenue_data(self):
        from_date = self.from_date.get().strip()
        to_date = self.to_date.get().strip()
        from_time = self.from_time.get().strip()
        to_time = self.to_time.get().strip()
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        query = '''
            SELECT b.id, p.name, b.bill_date, b.total_amount, b.discount_amount, b.paid_amount, b.remaining_amount, b.bill_number
            FROM bills b
            JOIN patients p ON b.patient_id = p.id
            WHERE DATE(b.bill_date) BETWEEN ? AND ?
            AND TIME(b.bill_date) BETWEEN ? AND ?
            ORDER BY b.bill_date DESC
        '''
        
        cursor.execute(query, (from_date, to_date, from_time, to_time))
        bills = cursor.fetchall()
        
        # Calculate totals
        cursor.execute('''
            SELECT COUNT(*), SUM(total_amount), SUM(paid_amount), SUM(discount_amount)
            FROM bills 
            WHERE DATE(bill_date) BETWEEN ? AND ?
            AND TIME(bill_date) BETWEEN ? AND ?
        ''', (from_date, to_date, from_time, to_time))
        
        summary = cursor.fetchone()
        total_bills = summary[0] if summary[0] else 0
        total_revenue = summary[1] if summary[1] else 0.0
        total_collected = summary[2] if summary[2] else 0.0
        total_discount = summary[3] if summary[3] else 0.0
        
        conn.close()
        
        # Update treeview
        self.revenue_tree.delete(*self.revenue_tree.get_children())
        for bill in bills:
            # Format date for display
            formatted_date = bill[2]
            if formatted_date:
                try:
                    formatted_date = datetime.datetime.strptime(bill[2], '%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y %H:%M')
                except:
                    pass
            self.revenue_tree.insert('', 'end', values=(
                bill[7] if bill[7] else f"BILL-{bill[0]}", bill[1], formatted_date, f"₹{bill[3]:.2f}", f"₹{bill[4]:.2f}", f"₹{bill[5]:.2f}", f"₹{bill[6]:.2f}"
            ))
        
        # Update summary labels
        self.total_bills_label.config(text=str(total_bills))
        self.total_revenue_label.config(text=f"₹{total_revenue:.2f}")
        self.total_collected_label.config(text=f"₹{total_collected:.2f}")
    
    def export_revenue_csv(self):
        filename = f"revenue_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['Bill ID', 'Patient Name', 'Date', 'Total Amount', 'Discount', 'Paid Amount', 'Remaining Amount'])
                
                for item in self.revenue_tree.get_children():
                    values = self.revenue_tree.item(item)['values']
                    writer.writerow(values)
            
            messagebox.showinfo("Success", f"Revenue report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV: {str(e)}")
    
    def export_revenue_pdf(self):
        filename = f"revenue_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        try:
            c = canvas.Canvas(filename, pagesize=letter)
            
            # Header
            c.setFont("Helvetica-Bold", 16)
            c.drawString(100, 750, "THAR PATHOLOGY LABORATORY - REVENUE REPORT")
            c.setFont("Helvetica", 12)
            c.drawString(100, 730, f"Period: {self.from_date.get()} to {self.to_date.get()}")
            c.drawString(100, 710, f"Time: {self.from_time.get()} to {self.to_time.get()}")
            c.drawString(100, 690, f"Contact: 03452869527 / +92 345 3879556")
            
            # Table header
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, 660, "Bill ID")
            c.drawString(120, 660, "Patient Name")
            c.drawString(280, 660, "Date")
            c.drawString(420, 660, "Amount")
            
            c.line(50, 655, 550, 655)
            
            # Table rows
            c.setFont("Helvetica", 10)
            y_position = 640
            total_revenue = 0.0
            
            for item in self.revenue_tree.get_children():
                values = self.revenue_tree.item(item)['values']
                c.drawString(50, y_position, str(values[0]))
                c.drawString(120, y_position, values[1])
                c.drawString(280, y_position, values[2])
                c.drawString(420, y_position, values[3])
                
                # Extract numeric value from amount string
                amount_str = values[3].replace('₹', '').replace(',', '')
                total_revenue += float(amount_str)
                y_position -= 20
                
                if y_position < 100:
                    c.showPage()
                    y_position = 750
                    c.setFont("Helvetica", 10)
            
            # Footer
            c.setFont("Helvetica-Bold", 12)
            c.drawString(300, y_position - 30, f"Total Revenue: ₹{total_revenue:.2f}")
            
            c.save()
            messagebox.showinfo("Success", f"Revenue report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF: {str(e)}")
    
    def add_user(self):
        if self.role != 'admin':
            messagebox.showerror("Error", "Only administrators can add users")
            return
            
        username = self.new_username.get().strip()
        password = self.new_password.get().strip()
        role = self.role_combo.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return
        
        if len(password) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters long")
            return
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = sqlite3.connect('lab_billing.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', 
                          (username, hashed_password, role))
            conn.commit()
            messagebox.showinfo("Success", "User added successfully")
            self.new_username.delete(0, tk.END)
            self.new_password.delete(0, tk.END)
            self.role_combo.set("user")
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists")
        finally:
            conn.close()
    
    def backup_database(self):
        if self.role != 'admin':
            messagebox.showerror("Error", "Only administrators can backup database")
            return
            
        import shutil
        try:
            backup_name = f"lab_billing_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2('lab_billing.db', backup_name)
            messagebox.showinfo("Success", f"Database backed up as {backup_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to backup database: {str(e)}")
    
    def reset_database(self):
        if self.role != 'admin':
            messagebox.showerror("Error", "Only administrators can reset database")
            return
            
        if messagebox.askyesno("Confirm", 
                              "This will delete all data except users. Continue?"):
            try:
                conn = sqlite3.connect('lab_billing.db')
                cursor = conn.cursor()
                
                # Delete all data but keep table structure and users
                cursor.execute('DELETE FROM bill_items')
                cursor.execute('DELETE FROM bills')
                cursor.execute('DELETE FROM patients')
                cursor.execute('DELETE FROM reports')
                
                # Add sample reports again
                sample_reports = [
                    ('Complete Blood Count', 500.00, '4 hours'),
                    ('Blood Glucose Test', 300.00, '2 hours'),
                    ('Lipid Profile', 800.00, '24 hours'),
                    ('Liver Function Test', 1200.00, '24 hours'),
                    ('Thyroid Test', 900.00, '24 hours'),
                    ('Urine Analysis', 250.00, '2 hours'),
                    ('X-Ray Chest', 600.00, '1 hour'),
                    ('ECG', 400.00, '30 minutes')
                ]
                cursor.executemany('INSERT INTO reports (name, price, expected_time) VALUES (?, ?, ?)', sample_reports)
                
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Database reset successfully")
                self.load_patients()
                self.load_reports_tree()
                self.load_reports()
                self.load_revenue_data()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset database: {str(e)}")

def main():
    root = tk.Tk()
    login_app = LoginWindow(root)
    root.mainloop()

if __name__ == "__main__":
    main()