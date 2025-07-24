#!/usr/bin/python3

# Wireless Explorer
# https://eax.me/wireless-explorer/
#
# Dependencies:
# sudo apt install python3-gi python3-gi-cairo python3-pygame

import pygame
import numpy
import os
import subprocess
import threading
import re

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk, GLib, GdkPixbuf, Gdk

class WirelessExplorer:
    def __init__(self):
        # Surface parameters
        self.pygame_width = 1600
        self.pygame_height = 300
        self.background_color = (0, 0, 0)
        self.foreground_color = (255, 255, 255)

        # Set of contrasting colors for networks
        self.network_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (255, 165, 0),  # Orange
            (255, 0, 255),  # Purple
            (0, 255, 255),  # Cyan
            (255, 255, 0),  # Yellow
            (255, 20, 147), # Pink
            (0, 191, 255),  # Blue
            (50, 205, 50),  # Lime
            (220, 20, 60),  # Crimson
            (128, 0, 128),  # Violet
            (255, 140, 0),  # Dark Orange
            (32, 178, 170), # Light Sea Green
            (255, 69, 0),   # Red-Orange
            (138, 43, 226), # Blue-Violet
            (0, 128, 0),    # Dark Green
            (255, 105, 180),# Hot Pink
            (30, 144, 255), # Dodger Blue
            (255, 215, 0),  # Gold
            (128, 128, 0),  # Olive
            (255, 0, 127),  # Rose
            (0, 255, 127),  # Spring Green
            (255, 127, 80), # Coral
            (148, 0, 211),  # Dark Violet
            (0, 206, 209),  # Dark Turquoise
            (255, 192, 203),# Light Pink
            (154, 205, 50), # Yellow Green
            (255, 99, 71),  # Tomato
            (72, 61, 139),  # Dark Slate Blue
            (255, 228, 181) # Moccasin
        ]

        pygame.init()
        self.font = pygame.font.Font(None, 24)

        # Create surface for rendering (initially fixed size)
        self.pygame_surface = pygame.Surface((self.pygame_width, self.pygame_height))
        self.current_pixbuf = None

        # Scanning state
        self.scanning_enabled = False
        self.scan_in_progress = False
        self.scan_timer_id = None

        # Network data storage for each tab
        self.tab_networks_data = {}

        # Create GTK interface
        self.setup_gtk()

    def setup_gtk(self):
        """Setup GTK interface"""
        self.window = Gtk.Window()
        self.window.set_title("Wireless Explorer")
        self.window.set_default_size(800, 600)
        self.window.connect("destroy", Gtk.main_quit)

        # Create main vertical container
        main_vbox = Gtk.VBox(spacing=0)
        self.window.add(main_vbox)

        # Create vertical paned (slider)
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        main_vbox.pack_start(self.paned, True, True, 0)

        # Create vertical container for top part
        top_vbox = Gtk.VBox(spacing=0)

        # Create toolbar
        toolbar_hbox = Gtk.HBox(spacing=10)
        toolbar_hbox.set_margin_start(10)
        toolbar_hbox.set_margin_end(10)
        toolbar_hbox.set_margin_top(5)
        toolbar_hbox.set_margin_bottom(5)

        # Left part of toolbar
        left_hbox = Gtk.HBox(spacing=10)

        # Text "Device:"
        device_label = Gtk.Label(label="Device:")
        left_hbox.pack_start(device_label, False, False, 0)

        # Device dropdown list
        self.device_combo = Gtk.ComboBoxText()

        # Get and add real Wi-Fi devices
        wifi_devices = self.get_wifi_devices()
        if wifi_devices:
            for device in wifi_devices:
               self.device_combo.append_text(device)
        else:
            self.device_combo.append_text("(none)")

        self.device_combo.set_active(0)

        # Connect device change handler
        self.device_combo.connect("changed", self.on_device_changed)
        left_hbox.pack_start(self.device_combo, False, False, 0)

        # Start/Stop button
        self.start_button = Gtk.Button(label="Start")
        self.start_button.connect("clicked", self.on_start_stop_clicked)
        left_hbox.pack_start(self.start_button, False, False, 0)

        # Right part of toolbar
        right_hbox = Gtk.HBox(spacing=5)

        # Text "Threshold:"
        threshold_label = Gtk.Label(label="Threshold:")
        right_hbox.pack_start(threshold_label, False, False, 0)

        # Number input field with arrows
        threshold_adjustment = Gtk.Adjustment(value=-130, lower=-130, upper=20, step_increment=1, page_increment=10, page_size=0)
        self.threshold_spin = Gtk.SpinButton(adjustment=threshold_adjustment, climb_rate=1, digits=0)
        right_hbox.pack_start(self.threshold_spin, False, False, 0)

        # Text "dBm"
        dbm_label = Gtk.Label(label="dBm")
        right_hbox.pack_start(dbm_label, False, False, 0)

        # Add left and right parts to main toolbar
        toolbar_hbox.pack_start(left_hbox, False, False, 0)
        toolbar_hbox.pack_end(right_hbox, False, False, 0)

        # Add toolbar to top container
        top_vbox.pack_start(toolbar_hbox, False, False, 0)

        # Add separator line
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        top_vbox.pack_start(separator, False, False, 0)

        # Create tab system for top part
        self.notebook = Gtk.Notebook()
        self.notebook.connect("switch-page", self.on_tab_switched)

        # Add notebook to top container
        top_vbox.pack_start(self.notebook, True, True, 0)

        # Add entire top container to paned
        self.paned.add1(top_vbox)

        # Create DrawingArea for displaying PyGame content
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.connect("draw", self.on_draw)
        self.drawing_area.connect("size-allocate", self.on_drawing_area_resize)
        self.paned.add2(self.drawing_area)

        # Create status bar
        self.status_bar = Gtk.Statusbar()
        self.status_context_id = self.status_bar.get_context_id("main")
        self.status_bar.push(self.status_context_id, "Ready.")
        main_vbox.pack_start(self.status_bar, False, False, 0)

        # Show window
        self.window.show_all()

        # Set paned position after showing window.
        # Practice shows it can work without idle_add(), but it's more reliable with it.
        GLib.idle_add(self._set_paned_position)

        # Initialize tabs and call handler for initially selected device
        # after all UI components are created
        self.update_tabs_for_device(None)
        self.on_device_changed(self.device_combo)

    def get_wifi_devices(self):
        """Gets list of Wi-Fi devices in the system"""
        devices = []
        try:
            # Try to get list via `iw dev`
            result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('Interface '):
                        device_name = line.split()[1]
                        devices.append(device_name)
        except Exception as e:
            print(f"get_wifi_devices() - {e}")
            pass

        return devices

    def _set_paned_position(self):
        """Sets paned to 50:50 position"""
        height = self.window.get_allocated_height()
        self.paned.set_position(height // 2)
        return False # Don't repeat this GLib.idle_add call

    def on_device_changed(self, combo):
        """Handler for selected device change"""
        selected_device = combo.get_active_text()
        self.update_tabs_for_device(selected_device)

        # Update status bar
        msg = "Ready."
        if selected_device and selected_device != "(none)":
            msg = f"Selected device: {selected_device}"

        self.status_bar.pop(self.status_context_id)
        self.status_bar.push(self.status_context_id, msg)

    def on_start_stop_clicked(self, button):
        """Handler for Start/Stop button click"""
        if self.scanning_enabled:
            # Stop scanning
            self.scanning_enabled = False
            if self.scan_timer_id:
                GLib.source_remove(self.scan_timer_id)
                self.scan_timer_id = None
            self.start_button.set_label("Start")
            self.status_bar.pop(self.status_context_id)
            self.status_bar.push(self.status_context_id, "Scanning stopped.")
        else:
            # Start scanning
            device_name = self.device_combo.get_active_text()
            if device_name and device_name != "(none)":
                self.scanning_enabled = True
                # Start scan timer every 5 seconds
                self.scan_timer_id = GLib.timeout_add(5000, self.scan_wifi_networks)
                self.start_button.set_label("Stop")
                self.status_bar.pop(self.status_context_id)
                self.status_bar.push(self.status_context_id, f"Scanning {device_name}...")
                # Start first scan immediately
                self.scan_wifi_networks()
            else:
                self.status_bar.pop(self.status_context_id)
                self.status_bar.push(self.status_context_id, "Please select a device first.")

    def on_tab_switched(self, notebook, page, page_num):
        """Tab switch handler"""
        # Get data for active tab and redraw surface
        networks_data = self.tab_networks_data.get(page_num, [])

        # Get selected network for specific tab
        selected_bssid = self.get_selected_network_bssid(page_num)

        # Draw with correct selection
        self.pygame_draw_networks_with_selection(networks_data, selected_bssid)
        self.schedule_drawing_area_update()

    def on_draw(self, widget, cr):
        """DrawingArea draw handler"""
        if self.current_pixbuf is None:
            return False

        # Get drawing area dimensions
        area_width = widget.get_allocated_width()
        area_height = widget.get_allocated_height()

        # Scale pixbuf to area dimensions
        if area_width > 0 and area_height > 0:
            scaled_pixbuf = self.current_pixbuf.scale_simple(
                area_width,
                area_height,
                GdkPixbuf.InterpType.BILINEAR
            )

            # Draw scaled pixbuf
            Gdk.cairo_set_source_pixbuf(cr, scaled_pixbuf, 0, 0)
            cr.paint()

        return False

    def on_drawing_area_resize(self, widget, allocation):
        """Drawing area resize handler"""
        self.pygame_width = max(allocation.width, 100)
        self.pygame_height = max(allocation.height, 100)

        # Create new surface
        self.pygame_surface = pygame.Surface((self.pygame_width, self.pygame_height))

        # Redraw content for current tab
        current_page = self.notebook.get_current_page()
        networks_data = self.tab_networks_data.get(current_page, [])
        self.pygame_draw_networks(networks_data)
        self.schedule_drawing_area_update()

    def update_tabs_for_device(self, device_name):
        """Updates tabs for selected device"""
        # Remove all existing pages
        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)

        if not device_name or device_name == "(none)":
            # If no device selected, show placeholder
            empty_label = Gtk.Label(label="")
            tab_label = Gtk.Label(label="(select device)")
            self.notebook.append_page(empty_label, tab_label)
        else:
            bands = self.get_device_bands(device_name)
            if bands:
                # Create tabs for each supported band
                for freq_band in sorted(bands):
                    # Create channel table instead of simple label
                    channels_table, table_model, treeview = self.create_channels_table()
                    tab_label = Gtk.Label(label=freq_band)
                    self.notebook.append_page(channels_table, tab_label)
            else:
                error_label = Gtk.Label(label="Unable to get frequency information for this device")
                tab_label = Gtk.Label(label="Error")
                self.notebook.append_page(error_label, tab_label)

        self.notebook.show_all()

        # Clear network data and PyGame surface when changing device
        self.tab_networks_data = {}
        self.pygame_draw_networks([])
        self.schedule_drawing_area_update()

    def create_channels_table(self):
        """Creates scrollable channel table"""
        # Create data model: BSSID, SSID, Channel, Frequency, Bandwidth, Signal
        liststore = Gtk.ListStore(str, str, str, str, str, str)

        # Create TreeView
        treeview = Gtk.TreeView(model=liststore)

        # Create columns
        # BSSID
        renderer_text = Gtk.CellRendererText()
        column_bssid = Gtk.TreeViewColumn("BSSID", renderer_text, text=0)
        column_bssid.set_resizable(True)
        column_bssid.set_expand(True)
        column_bssid.set_min_width(150)
        treeview.append_column(column_bssid)

        # SSID
        renderer_text = Gtk.CellRendererText()
        column_ssid = Gtk.TreeViewColumn("SSID", renderer_text, text=1)
        column_ssid.set_resizable(True)
        column_ssid.set_expand(True)
        column_ssid.set_min_width(150)
        treeview.append_column(column_ssid)

        # Channel
        renderer_text = Gtk.CellRendererText()
        column_channel = Gtk.TreeViewColumn("Channel", renderer_text, text=2)
        column_channel.set_resizable(True)
        column_channel.set_min_width(80)
        treeview.append_column(column_channel)

        # Frequency
        renderer_text = Gtk.CellRendererText()
        column_frequency = Gtk.TreeViewColumn("Frequency", renderer_text, text=3)
        column_frequency.set_resizable(True)
        column_frequency.set_min_width(100)
        treeview.append_column(column_frequency)

        # Bandwidth
        renderer_text = Gtk.CellRendererText()
        column_bw = Gtk.TreeViewColumn("Bandwidth", renderer_text, text=4)
        column_bw.set_resizable(True)
        column_bw.set_min_width(80)
        treeview.append_column(column_bw)

        # Signal
        renderer_text = Gtk.CellRendererText()
        column_signal = Gtk.TreeViewColumn("Signal", renderer_text, text=5)
        column_signal.set_resizable(True)
        column_signal.set_min_width(80)
        treeview.append_column(column_signal)

        # Add selection change handler
        selection = treeview.get_selection()
        selection.connect("changed", self.on_table_selection_changed)

        # Create ScrolledWindow for scrolling
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(treeview)

        return scrolled, liststore, treeview

    def on_table_selection_changed(self, selection):
        """Table selection change handler"""
        # Redraw frequency ruler with new selection
        current_page = self.notebook.get_current_page()
        networks_data = self.tab_networks_data.get(current_page, [])
        self.pygame_draw_networks(networks_data)
        self.schedule_drawing_area_update()

    def get_device_bands(self, device_name):
        """Gets information about supported bands for specified device"""
        bands = set()
        try:
            wiphy = self.device_get_wiphy(device_name)
            if wiphy is not None:
                result = subprocess.run(['iw', 'phy', f'phy{wiphy}', 'info'],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    bands = self.parse_phy_info_results(result.stdout)
        except Exception as e:
            print(f"get_device_bands() - {e}")
            pass

        return bands

    def device_get_wiphy(self, device_name):
        """Extracts wiphy value from `iw dev xxx info` output"""
        result = subprocess.run(['iw', 'dev', device_name, 'info'],
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'wiphy' in line:
                    return line.split()[-1]
        return None

    def parse_phy_info_results(self, info_output):
        """Parses `iw phy phyX info` output"""
        bands = set()
        lines = info_output.split('\n')
        current_band = None

        for line in lines:
            line_strip = line.strip()
            if line_strip.startswith('Band ') and ':' in line_strip:
                # We'll determine the actual frequency band when we see the first frequency
                current_band = "unknown"
            elif current_band == "unknown" and 'MHz' in line_strip and '[' in line_strip and ']' in line_strip:
                # Determine the actual band from the first frequency we see
                if 'disabled' not in line_strip.lower():
                    # Extract frequency number - format is "* 2412.0 MHz [1]..."
                    parts = line_strip.split()
                    for i, part in enumerate(parts):
                        if part.endswith('MHz'):
                            # The frequency is in the previous part
                            if i > 0:
                                freq_str = parts[i-1]
                                freq_num = float(freq_str)
                                current_band = self.get_frequency_band(freq_num)

                                # Add this band to our frequencies dict if it has active channels
                                if current_band not in bands:
                                    bands.add(current_band)
                                break
        return bands

    def scan_wifi_networks(self):
        """Starts Wi-Fi scanning in separate thread"""
        if not self.scanning_enabled:
            return True  # Continue timer, but scanning is disabled

        # Check if scan is already in progress
        if self.scan_in_progress:
            return True  # Continue timer

        device_name, band = self.get_current_device_and_band()
        if not device_name or not band:
            return True  # Continue timer

        # Update status bar
        self.status_bar.pop(self.status_context_id)
        self.status_bar.push(self.status_context_id, f"Scanning {device_name}...")

        # Start scanning in separate thread
        self.scan_in_progress = True
        thread = threading.Thread(target=self.scan_thread_proc, args=(device_name,))
        thread.daemon = True
        thread.start()

        return True  # Continue timer

    def get_current_device_and_band(self):
        """Gets currently selected device and frequency band"""
        device_name = self.device_combo.get_active_text()
        if not device_name or device_name == "(none)":
            return None, None

        # Get active tab index
        current_page = self.notebook.get_current_page()

        # Get tab name to determine band
        tab_label = self.notebook.get_tab_label_text(self.notebook.get_nth_page(current_page))

        return device_name, tab_label

    def get_selected_network_bssid(self, current_page):
        """Gets BSSID of selected network in specified or current table"""
        try:
            page = self.notebook.get_nth_page(current_page)
            treeview = page.get_child()
            selection = treeview.get_selection()
            tree_model, model_iter = selection.get_selected()
            return tree_model.get_value(model_iter, 0) # BSSID in first column
        except:
            pass
        return None

    def pygame_draw_networks(self, networks):
        page = self.notebook.get_current_page()
        selected_bssid = self.get_selected_network_bssid(page)
        self.pygame_draw_networks_with_selection(networks, selected_bssid)

    def pygame_draw_networks_with_selection(self, networks, selected_bssid):
        self.pygame_surface.fill(self.background_color)

        if not networks:
            empty_text = self.font.render("List is empty", True, self.foreground_color)
            text_rect = empty_text.get_rect(center=(self.pygame_width // 2, self.pygame_height // 2))
            self.pygame_surface.blit(empty_text, text_rect)
            return

        # Calculate frequency ranges
        freq_ranges = []
        for network in networks:
            freq = int(network['frequency'])
            bw = int(network['bandwidth'])
            freq_ranges.append((freq - bw/2, freq + bw/2, freq))

        # Find overall range
        min_freq = min(r[0] for r in freq_ranges)
        max_freq = max(r[1] for r in freq_ranges)

        # Ruler parameters
        ruler_y = self.pygame_height - 40
        ruler_left = 25
        ruler_right = self.pygame_width - 25
        ruler_width = ruler_right - ruler_left

        # Draw main ruler line
        pygame.draw.line(self.pygame_surface, self.foreground_color,
                        (ruler_left, ruler_y), (ruler_right, ruler_y), 2)

        # Draw ticks for each network
        drawn_freqs = set()  # Avoid duplicate labels
        for _, _, freq in freq_ranges:
            if freq in drawn_freqs:
                continue
            drawn_freqs.add(freq)

            # Calculate position on ruler
            pos_x = ruler_left + int((freq - min_freq) / (max_freq - min_freq) * ruler_width)

            # Draw tick
            pygame.draw.line(self.pygame_surface, self.foreground_color,
                           (pos_x, ruler_y - 10), (pos_x, ruler_y + 10), 2)

            # Draw frequency label
            freq_text = self.font.render(str(int(freq)), True, self.foreground_color)
            text_rect = freq_text.get_rect(center=(pos_x, ruler_y + 25))
            self.pygame_surface.blit(freq_text, text_rect)

        # Get threshold
        threshold = self.threshold_spin.get_value()

        # Find maximum signal for scaling
        max_signal = max(int(network['signal']) for network in networks)

        # Calculate maximum trapezoid height
        font_height = self.font.get_height()
        ruler_space = 50  # Space for ruler and labels
        max_tr_height = self.pygame_height - font_height - ruler_space

        # Draw each network, first with weak signals, then with strong ones
        for i, network in enumerate(reversed(networks)):
            freq = int(network['frequency'])
            bw = int(network['bandwidth'])
            signal = int(network['signal'])
            ssid = network['ssid']

            # Choose color cyclically. First network in list gets same color,
            # despite being drawn last
            color = self.network_colors[(len(networks)-i-1) % len(self.network_colors)]

            # Calculate left and right boundaries
            left_freq = freq - bw/2
            right_freq = freq + bw/2

            left_pos = ruler_left + int((left_freq - min_freq) / (max_freq - min_freq) * ruler_width)
            right_pos = ruler_left + int((right_freq - min_freq) / (max_freq - min_freq) * ruler_width)

            tr_width = max(right_pos - left_pos, 1)  # Minimum 1 pixel

            # Calculate height proportional to signal
            signal_range = max_signal - threshold
            if signal_range > 0:
                tr_height = int((signal - threshold) / signal_range * max_tr_height)
            else:
                tr_height = 1

            tr_height = max(tr_height, 1)  # Minimum 1 pixel

            # Calculate trapezoid coordinates
            top_inset = int(tr_width * 0.1)
            top_left = left_pos + top_inset
            top_right = right_pos - top_inset

            # If this is selected network, draw fill
            if selected_bssid and network.get('bssid') == selected_bssid:
                # Create semi-transparent surface
                fill_surface = pygame.Surface((self.pygame_width, self.pygame_height), pygame.SRCALPHA)
                fill_color = (*color, 80)  # Color with alpha channel (semi-transparency)

                # Draw filled trapezoid
                trapezoid_points = [
                    (left_pos, ruler_y),
                    (top_left, ruler_y - tr_height),
                    (top_right, ruler_y - tr_height),
                    (right_pos, ruler_y)
                ]
                pygame.draw.polygon(fill_surface, fill_color, trapezoid_points)

                # Blit to main surface
                self.pygame_surface.blit(fill_surface, (0, 0))

            # Draw trapezoid outline - 3 sides without bottom
            # Left side
            pygame.draw.aaline(self.pygame_surface, color,
                            (left_pos, ruler_y), (top_left, ruler_y - tr_height))
            # Right side
            pygame.draw.aaline(self.pygame_surface, color,
                            (right_pos, ruler_y), (top_right, ruler_y - tr_height))
            # Top side, narrowed
            pygame.draw.line(self.pygame_surface, color,
                            (top_left, ruler_y - tr_height), (top_right, ruler_y - tr_height), 2)

            # Draw SSID above rectangle
            if ssid != '(hidden)':
                ssid_text = self.font.render(ssid, True, color, self.background_color)
                text_center_x = (left_pos + right_pos) // 2
                text_y = ruler_y - tr_height - font_height - 5

                # Make sure text doesn't go beyond boundaries
                text_rect = ssid_text.get_rect()
                text_rect.centerx = text_center_x
                text_rect.y = max(text_y, 5)  # Minimum 5 pixels from top

                self.pygame_surface.blit(ssid_text, text_rect)

    def schedule_drawing_area_update(self):
        """Converts Surface to GdkPixbuf and schedules drawing_area redraw"""
        # Get pixel array from pygame surface
        pygame_array = pygame.surfarray.array3d(self.pygame_surface)

        # PyGame uses (width, height, channels), but GdkPixbuf expects (height, width, channels)
        pygame_array = numpy.transpose(pygame_array, (1, 0, 2))

        # Add alpha channel (RGBA)
        height, width, channels = pygame_array.shape
        rgba_array = numpy.zeros((height, width, 4), dtype=numpy.uint8)
        rgba_array[:, :, :3] = pygame_array
        rgba_array[:, :, 3] = 255  # Full opacity

        # Create GdkPixbuf from array
        self.current_pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            rgba_array.tobytes(),
            GdkPixbuf.Colorspace.RGB,
            True,  # has_alpha
            8,     # bits_per_sample
            width,
            height,
            width * 4  # rowstride
        )

        self.drawing_area.queue_draw()

    def scan_thread_proc(self, device_name):
        """Performs scanning in separate thread"""
        try:
            result = subprocess.run(['iw', 'dev', device_name, 'scan'],
                                  capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Parse scan results for all bands
                networks = self.parse_scan_results(result.stdout)
                # Safely update UI via GLib.idle_add
                GLib.idle_add(self._update_scan_results, networks)
            else:
                GLib.idle_add(self._scan_completed)

        except Exception as e:
            print(f"scan_thread_proc() - {e}")
            GLib.idle_add(self._scan_completed)

    def parse_scan_results(self, scan_output):
        """Parses `iw scan` results using regex"""
        networks = []

        # Split into BSS blocks
        bss_blocks = re.split(r'\nBSS ', scan_output)

        for block in bss_blocks:
            if not block.strip():
                continue

            bssid_match = re.search(r'^(?:BSS )?([a-f0-9:]{17})', block)
            freq_match = re.search(r'freq:\s*(\d+)', block)
            ssid_match = re.search(r'SSID:\s*(.+)', block)
            signal_match = re.search(r'signal:\s*(-?\d+).*dBm', block)
            channel_match = re.search(r'primary channel:\s*(\d+)', block)
            bw_match = re.search(r'channel width:\s*(\d+)', block)

            frequency = freq_match.group(1).strip() if freq_match else '0'

            network = {
                'bssid': bssid_match.group(1) if bssid_match else '?',
                'ssid': ssid_match.group(1).strip() if ssid_match else '(hidden)',
                'channel': channel_match.group(1) if channel_match else '?',
                'frequency': frequency,
                'bandwidth': bw_match.group(1) if bw_match else '20',
                'signal': signal_match.group(1) if signal_match else '-130'
            }

            if network['bandwidth'] == '0':
                # special case: "* channel width: 0 (20 or 40 MHz)"; assume worst
                network['bandwidth'] = '40'
            elif network['bandwidth'] == '1':
                # special case: "* channel width: 1 (80 MHz)"
                network['bandwidth'] = '80'

            networks.append(network)

        return networks

    def _update_scan_results(self, networks):
        """Updates scan results in UI (called from main thread)"""
        if not self.scanning_enabled:
            return

        # Group networks by frequency bands
        networks_by_band = {'2.4 GHz': [], '5 GHz': [], '6 GHz': []}

        for network in networks:
            freq = int(network['frequency'])
            band = self.get_frequency_band(freq)
            if band:
                networks_by_band[band].append(network)

        # Get threshold for filtering
        threshold = self.threshold_spin.get_value()

        # Update all tabs
        for tab_index in range(self.notebook.get_n_pages()):
            tab_label = self.notebook.get_tab_label_text(self.notebook.get_nth_page(tab_index))
            band_networks = networks_by_band[tab_label]

            # Sort by descending signal
            band_networks.sort(key=lambda x: int(x['signal']), reverse=True)

            # Filter by threshold
            filtered_networks = [network for network in band_networks if int(network['signal']) >= threshold]

            # Update table and save data
            self.update_channels_table(tab_index, filtered_networks)
            self.tab_networks_data[tab_index] = filtered_networks

        # Update PyGame surface for current active tab
        current_page = self.notebook.get_current_page()
        current_networks = self.tab_networks_data.get(current_page, [])
        self.pygame_draw_networks(current_networks)
        self.schedule_drawing_area_update()

        self._scan_completed()

    def _scan_completed(self):
        """Marks scanning as completed"""
        self.scan_in_progress = False
        # Update status bar
        self.status_bar.pop(self.status_context_id)
        self.status_bar.push(self.status_context_id, "Ready.")
        return False  # Don't repeat this GLib.idle_add call

    def get_frequency_band(self, frequency):
        """Determines frequency band by frequency"""
        if 2400 <= frequency <= 2500:
            return "2.4 GHz"
        elif 5000 <= frequency <= 6000:
            return "5 GHz"
        elif 6000 <= frequency <= 7000:
            return "6 GHz"
        return None

    def update_channels_table(self, tab_index, networks):
        """Updates channel table content on specified tab"""

        # Get TreeView and Model directly from widget hierarchy
        page = self.notebook.get_nth_page(tab_index)
        treeview = page.get_child()  # ScrolledWindow -> TreeView
        model = treeview.get_model()

        # Remember selected BSSID before update
        selected_bssid = None
        selection = treeview.get_selection()
        tree_model, model_iter = selection.get_selected()
        if model_iter and tree_model:
            selected_bssid = tree_model.get_value(model_iter, 0)  # BSSID in first column

        model.clear()
        for net in networks:
            row_data = [
                net['bssid'],
                net['ssid'],
                net['channel'],
                net['frequency'],
                net['bandwidth'],
                net['signal'],
            ]
            model.append(row_data)

        # Restore selection if network with same BSSID is found
        if selected_bssid:
            tree_iter = model.get_iter_first()
            while tree_iter:
                if model.get_value(tree_iter, 0) == selected_bssid:
                    selection.select_iter(tree_iter)
                    break
                tree_iter = model.iter_next(tree_iter)

    def run(self):
        Gtk.main()

app = WirelessExplorer()
app.run()
# Keep this! Workaround for https://github.com/pygame/pygame/issues/329
os._exit(0)
