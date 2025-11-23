import tkinter as tk
import threading
from overlay import ControlPanel
from tracker import CardTracker

def main():
    root = tk.Tk()
    # Root is just a container, we hide it or use it as controller
    root.withdraw() # Hide the main root window, we use ControlPanel and Overlay
    
    # Create Controller Window
    # We need a new Toplevel for control panel since root is hidden, 
    # OR we just use root as control panel. Let's use root as control panel.
    root.deiconify()
    
    tracker = None
    tracker_thread = None
    
    def start_tracking():
        nonlocal tracker, tracker_thread
        if tracker is None:
            tracker = CardTracker(app) # Pass app to access overlay and debug flag
        
        tracker.running = True
        tracker_thread = threading.Thread(target=tracker.run_loop, daemon=True)
        tracker_thread.start()
        
    def stop_tracking():
        nonlocal tracker
        if tracker:
            tracker.stop()

    def reset_tracking():
        nonlocal tracker
        if tracker:
            tracker.reset()
        else:
            # If tracker not created yet, just clear overlay
            app.overlay.clear_marks()
            
    app = ControlPanel(root, start_tracking, stop_tracking, reset_tracking)
    
    root.mainloop()

if __name__ == "__main__":
    main()
