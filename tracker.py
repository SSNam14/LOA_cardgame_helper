import mss
import numpy as np
from PIL import Image
import time

class CardTracker:
    def __init__(self, app_ref):
        self.app = app_ref
        self.overlay = app_ref.overlay
        self.running = False
        self.card_states = {} # (row, col) -> 'UNKNOWN', 'GOLD', 'OTHER'
        self.best_gold_counts = {} # (row, col) -> max_count
        
        # Color definitions
        # Gold: #C17E25 -> RGB(193, 126, 37)
        self.TARGET_COLOR = (193, 126, 37)
        self.COLOR_TOLERANCE = 5
        
        # Brightness Threshold for Flipped vs Face Down
        # Face down is #040001 (very dark)
        # Flipped is "much brighter"
        self.BRIGHTNESS_THRESHOLD = 20 

    def reset(self):
        self.card_states = {}
        self.best_gold_counts = {} # (row, col) -> max_count
        self.stability_cache = {}
        self.overlay.clear_marks()

    def start(self):
        self.running = True
        self.run_loop()

    def stop(self):
        self.running = False

    def run_loop(self):
        with mss.mss() as sct:
            while self.running:
                start_time = time.time()
                
                # Optimize: Capture the entire grid area once
                # We need the bounding box of all cards
                # Top-left of (0,0)
                r0_c0 = self.overlay.get_card_region(0, 0)
                # Bottom-right of (2,5)
                r2_c5 = self.overlay.get_card_region(2, 5)
                
                # mss monitor dict
                monitor = {
                    'top': r0_c0['top'],
                    'left': r0_c0['left'],
                    'width': (r2_c5['left'] + r2_c5['width']) - r0_c0['left'],
                    'height': (r2_c5['top'] + r2_c5['height']) - r0_c0['top']
                }
                
                # Capture full grid
                full_grid_img = self.capture_region(sct, monitor)
                full_grid_arr = np.array(full_grid_img)
                
                # Iterate over all cards
                for r in range(3):
                    for c in range(6):
                        # Calculate relative coordinates for cropping
                        # We can't use get_card_region directly because it returns global coords
                        # We need coords relative to the monitor['left'], monitor['top']
                        
                        # Re-calculate card position based on overlay config
                        # This duplicates some logic but avoids threading issues with calling overlay methods too often
                        # Ideally overlay should provide relative coords, but let's calculate:
                        
                        # Global coords of this card
                        card_global = self.overlay.get_card_region(r, c)
                        
                        # Relative to captured grid
                        rel_x = card_global['left'] - monitor['left']
                        rel_y = card_global['top'] - monitor['top']
                        rel_w = card_global['width']
                        rel_h = card_global['height']
                        
                        # Crop card image
                        # Check bounds
                        if rel_x < 0 or rel_y < 0 or rel_x + rel_w > full_grid_arr.shape[1] or rel_y + rel_h > full_grid_arr.shape[0]:
                            continue
                            
                        card_arr = full_grid_arr[rel_y:rel_y+rel_h, rel_x:rel_x+rel_w]
                        img = Image.fromarray(card_arr) # Convert back to PIL for existing methods if needed, or keep as arr
                        
                        # --- Stability Check ---
                        # Key: (r, c)
                        # We store: {'last_arr': np_array, 'stable_frames': int}
                        if not hasattr(self, 'stability_cache'):
                            self.stability_cache = {}
                            
                        cache = self.stability_cache.get((r, c), {'last_arr': None, 'stable_frames': 0})
                        
                        is_stable = False
                        is_stable = False
                        if cache['last_arr'] is not None:
                            # Check if shapes match (user might have changed config)
                            if cache['last_arr'].shape == card_arr.shape:
                                # Calculate difference
                                # Simple mean absolute difference
                                diff = np.mean(np.abs(card_arr - cache['last_arr']))
                                
                                # Threshold for "very little change". 
                                # 2-3 pixel value average diff is usually noise/minor shifts.
                                if diff < 5.0:
                                    cache['stable_frames'] += 1
                                else:
                                    cache['stable_frames'] = 0
                            else:
                                # Shape mismatch, reset
                                cache['stable_frames'] = 0
                        else:
                            cache['stable_frames'] = 0
                            
                        # Update cache
                        cache['last_arr'] = card_arr
                        self.stability_cache[(r, c)] = cache
                        
                        # User requirement: "2 frames or more with very little change"
                        # So stable_frames >= 2
                        if cache['stable_frames'] >= 2:
                            is_stable = True
                        
                        # --- Analysis ---
                        # Only process if stable (to avoid ghosting)
                        if is_stable:
                            is_flipped = self.check_flipped(card_arr) # Updated to accept array
                            
                            if is_flipped:
                                gold_count = self.count_gold_pixels(card_arr) # Updated to accept array
                                
                                # If this is a "Gold" card (has significant gold pixels)
                                if gold_count > self.overlay.gold_threshold:
                                    current_best = self.best_gold_counts.get((r, c), 0)
                                    
                                    # If this frame has more gold detail than before, update the overlay
                                    if gold_count > current_best:
                                        self.best_gold_counts[(r, c)] = gold_count
                                        self.card_states[(r, c)] = 'GOLD'
                                        
                                        # Create faint overlay image
                                        # Crop from scan_y_end to bottom (below the scan strip)
                                        crop_y = self.overlay.scan_y_end
                                        
                                        # Crop is relative to card height.
                                        # card_arr is (h, w, 3)
                                        if card_arr.shape[0] > crop_y:
                                            crop_arr = card_arr[crop_y:, :, :]
                                            overlay_img = Image.fromarray(crop_arr)
                                            
                                            # Add alpha channel for transparency (use configured alpha)
                                            overlay_img.putalpha(self.overlay.overlay_alpha) 
                                            
                                            # Debug logic removed as requested
                                            
                                            self.overlay.update_card_image(r, c, overlay_img, y_offset=crop_y)
                            else:
                                # Card is face down
                                pass
                            
                # Sleep to maintain ~30 FPS (0.033s)
                elapsed = time.time() - start_time
                if elapsed < 0.033:
                    time.sleep(0.033 - elapsed)
                # self.overlay.update() # Removed as we use after() in overlay

    def capture_region(self, sct, region):
        # mss region: {'top': y, 'left': x, 'width': w, 'height': h}
        screenshot = sct.grab(region)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def check_flipped(self, img_or_arr):
        # Calculate average brightness
        if isinstance(img_or_arr, Image.Image):
            arr = np.array(img_or_arr)
        else:
            arr = img_or_arr
            
        avg_brightness = np.mean(arr)
        return avg_brightness > self.BRIGHTNESS_THRESHOLD

    def count_gold_pixels(self, img_or_arr):
        # Scan only the specific strip: y=start to end
        if isinstance(img_or_arr, Image.Image):
            arr = np.array(img_or_arr)
        else:
            arr = img_or_arr
        
        h, w, _ = arr.shape
        
        # Get scan range from overlay config
        scan_start = self.overlay.scan_y_start
        scan_end = self.overlay.scan_y_end
        
        y_start = min(scan_start, h)
        y_end = min(scan_end, h)
        
        if y_start == y_end:
            return 0
            
        strip = arr[y_start:y_end, :, :]
        
        # Target Colors:
        # 1. #B47834 -> RGB(180, 120, 52)
        # 2. #C17E25 -> RGB(193, 126, 37)
        # We will check if pixel matches ANY of these with tolerance
        targets = [
            (180, 120, 52),
            (193, 126, 37)
        ]
        tolerance = 15 # Increased tolerance as requested ("much wider")
        
        combined_mask = np.zeros(strip.shape[:2], dtype=bool)
        
        for target in targets:
            lower = np.array([max(0, c - tolerance) for c in target])
            upper = np.array([min(255, c + tolerance) for c in target])
            
            mask = np.all((strip >= lower) & (strip <= upper), axis=-1)
            combined_mask = combined_mask | mask
            
        return np.sum(combined_mask)

    def check_gold(self, img):
        # Deprecated, using count_gold_pixels directly
        # Threshold might need adjustment since we scan fewer pixels now
        # Strip is 11 pixels high * ~140 width = ~1500 pixels.
        # Let's keep threshold low, maybe 10?
        return self.count_gold_pixels(img) > 10
