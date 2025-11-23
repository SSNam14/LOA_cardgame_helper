import tkinter as tk
from ctypes import windll

class CardOverlay(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Card Helper Overlay")
        self.attributes('-alpha', 1.0) # Full opacity window, control image alpha individually
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', 'white')
        
        # Initial Geometry - can be adjusted
        self.geometry("1200x900")
        
        self.canvas = tk.Canvas(self, width=1200, height=900, bg='white', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        
        # Card Grid Configuration
        # Actual card size for pitch calculation
        self.cell_w = 151
        self.cell_h = 232
        
        # Visual/Detection size (padded)
        self.card_w = 141
        self.card_h = 222
        self.padding_x = 7
        self.padding_y = 7
        
        self.gap_x = 0 
        self.gap_y = 0 
        self.start_x = 50
        self.start_y = 50
        
        self.rows = 3
        self.cols = 6
        
        self.overlay_alpha = 230 # Fixed opacity as requested
        
        self.click_through = False
        
        # Resolution Presets
        self.presets = {
            'FHD': {
                'cell_w': 151, 'cell_h': 232,
                'padding': 7,
                'scan_y_start': 168, 'scan_y_end': 179,
                'gold_threshold': 10
            },
            'QHD': {
                'cell_w': 202, 'cell_h': 310,
                'padding': 9, # 7 * 1.33
                'scan_y_start': 224, 'scan_y_end': 239, # 168*1.336, 179*1.336
                'gold_threshold': 18 # 10 * 1.78 (area ratio)
            }
        }
        
        self.current_res = 'FHD'
        self.apply_preset('FHD')
        
        self.draw_grid()
        self.maintain_style()

    def apply_preset(self, res_name):
        preset = self.presets[res_name]
        self.cell_w = preset['cell_w']
        self.cell_h = preset['cell_h']
        self.padding_x = preset['padding']
        self.padding_y = preset['padding']
        self.scan_y_start = preset['scan_y_start']
        self.scan_y_end = preset['scan_y_end']
        self.gold_threshold = preset['gold_threshold']
        
        # Update visual size
        self.card_w = self.cell_w - (2 * self.padding_x)
        self.card_h = self.cell_h - (2 * self.padding_y)
        
        # Calculate Grid Size
        grid_w = (self.cols * self.cell_w) + (self.cols - 1) * self.gap_x
        grid_h = (self.rows * self.cell_h) + (self.rows - 1) * self.gap_y
        
        # Calculate Margins (5% of grid size)
        self.start_x = int(grid_w * 0.05)
        self.start_y = int(grid_h * 0.05)
        
        # Calculate Required Window Size
        req_w = grid_w + (2 * self.start_x)
        req_h = grid_h + (2 * self.start_y)
        
        # Resize Window and Canvas
        # Center the window on screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - req_w) // 2
        y = (screen_h - req_h) // 2
        
        self.geometry(f"{req_w}x{req_h}+{x}+{y}")
        self.canvas.config(width=req_w, height=req_h)

    def maintain_style(self):
        # Periodically enforce click-through if enabled
        if self.click_through:
            self.set_click_through(True)
        self.after(1000, self.maintain_style)
        
    def draw_grid(self):
        self.canvas.delete('grid')
        self.canvas.delete('overlay')
        
        for r in range(self.rows):
            for c in range(self.cols):
                # Calculate based on cell pitch
                cell_x = self.start_x + c * (self.cell_w + self.gap_x)
                cell_y = self.start_y + r * (self.cell_h + self.gap_y)
                
                # Apply padding for the visual box
                x1 = cell_x + self.padding_x
                y1 = cell_y + self.padding_y
                x2 = x1 + self.card_w
                y2 = y1 + self.card_h
                
                # Draw frame for alignment
                self.canvas.create_rectangle(x1, y1, x2, y2, outline='blue', width=2, tags='grid')
                
                # Debug: Show scan area
                scan_y1 = y1 + self.scan_y_start
                scan_y2 = y1 + self.scan_y_end
                self.canvas.create_rectangle(x1, scan_y1, x2, scan_y2, outline='red', width=1, tags='grid')
                
    def mark_gold_card(self, row, col):
        pass

    def update_card_image(self, row, col, pil_image, y_offset=0):
        def _update():
            # Calculate based on cell pitch
            cell_x = self.start_x + col * (self.cell_w + self.gap_x)
            cell_y = self.start_y + row * (self.cell_h + self.gap_y)
            
            # Apply padding
            x = cell_x + self.padding_x
            y = cell_y + self.padding_y + y_offset
            
            # Convert PIL to ImageTk
            from PIL import ImageTk
            tk_img = ImageTk.PhotoImage(pil_image)
            
            # Store reference to prevent GC
            if not hasattr(self, 'card_images'):
                self.card_images = {}
            self.card_images[(row, col)] = tk_img
            
            # Remove old image/text if any
            self.canvas.delete(f'card_img_{row}_{col}')
            self.canvas.delete(f'gold_{row}_{col}')
            
            # Draw new image
            self.canvas.create_image(x, y, image=tk_img, anchor='nw', tags=f'card_img_{row}_{col}')
            
        self.after(0, _update)

    def clear_marks(self):
        def _clear():
            self.canvas.delete('gold')
            self.canvas.delete('card_img') # Delete all images with this tag
            if hasattr(self, 'card_images'):
                self.card_images.clear()
        self.after(0, _clear)

    def set_click_through(self, enable):
        self.click_through = enable
        try:
            hwnd = windll.user32.GetParent(self.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            
            style = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            if enable:
                new_style = style | WS_EX_TRANSPARENT | WS_EX_LAYERED
            else:
                new_style = style & ~WS_EX_TRANSPARENT
            
            if style != new_style:
                windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                # Force update but be careful not to steal focus or cause flicker
                windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x27) # SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
        except Exception as e:
            print(f"Error setting click-through: {e}")

    def get_card_region(self, row, col):
        # Returns global screen coordinates for a card
        cell_x = self.winfo_rootx() + self.start_x + col * (self.cell_w + self.gap_x)
        cell_y = self.winfo_rooty() + self.start_y + row * (self.cell_h + self.gap_y)
        
        x = cell_x + self.padding_x
        y = cell_y + self.padding_y
        
        return {'top': y, 'left': x, 'width': self.card_w, 'height': self.card_h}

class ControlPanel:
    def __init__(self, root, on_start, on_stop, on_reset):
        self.root = root
        self.root.title("Controls")
        self.root.geometry("350x400")
        self.root.attributes('-topmost', True)
        
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_reset = on_reset
        
        self.overlay = CardOverlay(root)
        
        # --- Resolution Selection ---
        res_frame = tk.LabelFrame(root, text="Resolution", padx=5, pady=5)
        res_frame.pack(fill='x', padx=10, pady=5)
        
        self.var_res = tk.StringVar(value="FHD")
        tk.Radiobutton(res_frame, text="FHD (1080p)", variable=self.var_res, value="FHD", command=self.change_resolution).pack(side='left', padx=10)
        tk.Radiobutton(res_frame, text="QHD (1440p)", variable=self.var_res, value="QHD", command=self.change_resolution).pack(side='left', padx=10)
        
        # --- Configuration Controls ---
        config_frame = tk.LabelFrame(root, text="Manual Adjust (Optional)", padx=5, pady=5)
        config_frame.pack(fill='x', padx=10, pady=5)
        
        # Gap X
        tk.Label(config_frame, text="Gap X:").grid(row=0, column=0, sticky='e')
        self.var_gx = tk.IntVar(value=self.overlay.gap_x)
        tk.Spinbox(config_frame, from_=0, to=50, textvariable=self.var_gx, width=5, command=self.update_config).grid(row=0, column=1)
        
        # Gap Y
        tk.Label(config_frame, text="Gap Y:").grid(row=0, column=2, sticky='e')
        self.var_gy = tk.IntVar(value=self.overlay.gap_y)
        tk.Spinbox(config_frame, from_=0, to=50, textvariable=self.var_gy, width=5, command=self.update_config).grid(row=0, column=3)
        
        # Apply Button
        tk.Button(config_frame, text="Apply Gaps", command=self.update_config).grid(row=1, column=0, columnspan=4, pady=5)

        # --- Main Controls ---
        tk.Button(root, text="START Monitoring (Locks Overlay)", command=self.start, bg='green', fg='white', font=('Arial', 10, 'bold')).pack(pady=10, fill='x', padx=10)
        tk.Button(root, text="UNLOCK / STOP (Enable Move)", command=self.stop, bg='red', fg='white', font=('Arial', 10, 'bold')).pack(pady=5, fill='x', padx=10)
        tk.Button(root, text="RESET Memory", command=self.reset, bg='orange', fg='black').pack(pady=10, fill='x', padx=10)
        
        self.status = tk.Label(root, text="Stopped - Overlay Movable", fg='blue')
        self.status.pack()
        
        # Instructions
        tk.Label(root, text="Select Resolution -> Align Blue Boxes -> START", justify='center', fg='gray').pack(pady=10, padx=10)

    def change_resolution(self):
        res = self.var_res.get()
        self.overlay.apply_preset(res)
        self.overlay.draw_grid()

    def update_config(self):
        self.overlay.gap_x = self.var_gx.get()
        self.overlay.gap_y = self.var_gy.get()
        self.overlay.draw_grid()

    def reset(self):
        if self.on_reset:
            self.on_reset()

    def start(self):
        self.overlay.set_click_through(True)
        self.status.config(text="Running - Overlay LOCKED (Click-Through)", fg='green')
        self.on_start()

    def stop(self):
        self.overlay.set_click_through(False)
        self.status.config(text="Stopped - Overlay Movable", fg='blue')
        self.on_stop()
