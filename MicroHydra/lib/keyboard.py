import machine

"""
lib.keyboard version: 2.0 (TCA8418 for Cardputer ADV)
changes:
    Replaced shift-register scanning with TCA8418 I2C driver.
    Compatible with MicroHydra API.
"""

# TCA8418 Registers
_REG_CFG = const(0x01)
_REG_INT_STAT = const(0x02)
_REG_KEY_EVENT_A = const(0x04)
_REG_KP_GPIO1 = const(0x1D)
_REG_KP_GPIO2 = const(0x1E)
_REG_KP_GPIO3 = const(0x1F)

# Modifier Key IDs
_KC_FN = const(3)
_KC_SHIFT = const(7)
_KC_CTRL = const(4)
_KC_ALT = const(14)
_KC_OPT = const(8)

# Key Maps: ID -> (Base, Shift, Fn)
# Matches original MicroHydra key names
keymap = {
    # Col 1
    1: ('ESC', 'ESC', 'ESC'),
    2: ('TAB', 'TAB', 'TAB'),
    3: (None, None, None),  # FN
    4: ('CTL', 'CTL', 'CTL'),  # CTRL
    
    # Col 2
    5: ('1', '!', 'F1'),
    6: ('q', 'Q', None),
    7: (None, None, None),  # SHIFT
    8: ('OPT', 'OPT', 'OPT'),  # OPT
    
    # Col 3
    11: ('2', '@', 'F2'),
    12: ('w', 'W', None),
    13: ('a', 'A', None),
    14: ('ALT', 'ALT', 'ALT'),  # ALT
    
    # Col 4
    15: ('3', '#', 'F3'),
    16: ('e', 'E', None),
    17: ('s', 'S', None),
    18: ('z', 'Z', None),
    
    # Col 5
    21: ('4', '$', 'F4'),
    22: ('r', 'R', None),
    23: ('d', 'D', None),
    24: ('x', 'X', None),
    
    # Col 6
    25: ('5', '%', 'F5'),
    26: ('t', 'T', None),
    27: ('f', 'F', None),
    28: ('c', 'C', None),
    
    # Col 7
    31: ('6', '^', 'F6'),
    32: ('y', 'Y', None),
    33: ('g', 'G', None),
    34: ('v', 'V', None),
    
    # Col 8
    35: ('7', '&', 'F7'),
    36: ('u', 'U', None),
    37: ('h', 'H', None),
    38: ('b', 'B', None),
    
    # Col 9
    41: ('8', '*', 'F8'),
    42: ('i', 'I', None),
    43: ('j', 'J', None),
    44: ('n', 'N', None),
    
    # Col 10
    45: ('9', '(', 'F9'),
    46: ('o', 'O', None),
    47: ('k', 'K', None),
    48: ('m', 'M', None),
    
    # Col 11
    51: ('0', ')', 'F10'),
    52: ('p', 'P', None),
    53: ('l', 'L', 'UP'),  # Fn+L = Arrow Up
    54: (',', '<', None),
    
    # Col 12
    55: ('-', '_', None),
    56: ('[', '{', None),
    57: (';', ':', 'LEFT'),  # Fn+; = Arrow Left
    58: ('.', '>', 'DOWN'),  # Fn+. = Arrow Down
    
    # Col 13
    61: ('=', '+', None),
    62: (']', '}', None),
    63: ("'", '"', None),
    64: ('/', '?', 'RIGHT'),  # Fn+/ = Arrow Right
    
    # Col 14
    65: ('BSPC', 'BSPC', 'DEL'),  # Backspace / Delete
    66: ('\\', '|', None),
    67: ('ENT', 'ENT', 'ENT'),  # Enter
    68: ('SPC', 'SPC', 'SPC'),  # Space
}


class KeyBoard:
    def __init__(self):
        # I2C for TCA8418
        self.i2c = machine.I2C(0, sda=machine.Pin(8), scl=machine.Pin(9), freq=400000)
        self.addr = 0x34
        
        # State tracking
        self.key_state = []
        self.prev_key_state = []
        self._shift_held = False
        self._fn_held = False
        
        # "Go" button on Pin 0 (original Cardputer feature)
        self.go = machine.Pin(0, machine.Pin.IN, machine.Pin.PULL_UP)
        
        # Initialize TCA8418
        self._init_chip()
    
    def _init_chip(self):
        try:
            # Enable all rows and columns for matrix
            self.i2c.writeto_mem(self.addr, _REG_KP_GPIO1, b'\xFF')
            self.i2c.writeto_mem(self.addr, _REG_KP_GPIO2, b'\xFF')
            self.i2c.writeto_mem(self.addr, _REG_KP_GPIO3, b'\x03')
            # Config: AI=1, KE_IEN=1, GPI_IEN=1
            self.i2c.writeto_mem(self.addr, _REG_CFG, b'\x83')
        except Exception as e:
            print(f"TCA8418 init error: {e}")
    
    def _read_events(self):
        """Read all pending key events from FIFO."""
        events = []
        try:
            # Check if there are events
            status = self.i2c.readfrom_mem(self.addr, _REG_INT_STAT, 1)[0]
            while status & 0x01:  # Key event flag
                event = self.i2c.readfrom_mem(self.addr, _REG_KEY_EVENT_A, 1)[0]
                if event == 0:
                    break
                events.append(event)
                # Clear interrupt
                self.i2c.writeto_mem(self.addr, _REG_INT_STAT, b'\x01')
                status = self.i2c.readfrom_mem(self.addr, _REG_INT_STAT, 1)[0]
        except:
            pass
        return events
    
    def get_pressed_keys(self):
        """Get a readable list of currently held keys."""
        self.key_state = []
        
        # Check "GO" button
        if self.go.value() == 0:
            self.key_state.append("GO")
        
        # Process TCA8418 events
        events = self._read_events()
        for event in events:
            key_id = event & 0x7F
            is_press = (event & 0x80) > 0
            
            # Track modifiers
            if key_id == _KC_SHIFT:
                self._shift_held = is_press
                continue
            elif key_id == _KC_FN:
                self._fn_held = is_press
                continue
            elif key_id in (_KC_CTRL, _KC_ALT, _KC_OPT):
                # Add modifier key names on press
                if is_press and key_id in keymap:
                    self.key_state.append(keymap[key_id][0])
                continue
            
            # Regular keys - only add on press
            if is_press and key_id in keymap:
                base, shift, fn = keymap[key_id]
                if self._fn_held and fn:
                    self.key_state.append(fn)
                elif self._shift_held and shift:
                    self.key_state.append(shift)
                elif base:
                    self.key_state.append(base)
        
        return self.key_state
    
    def get_new_keys(self):
        """Return a list of keys which are newly pressed."""
        self.prev_key_state = self.key_state.copy()
        self.get_pressed_keys()
        return [key for key in self.key_state if key not in self.prev_key_state]


if __name__ == "__main__":
    import time
    kb = KeyBoard()
    for _ in range(0, 400):
        print(kb.get_new_keys())
        time.sleep_ms(10)
