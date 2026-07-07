
from typing import Dict, Any

TILES: Dict[str, Dict[int, Dict[str, Any]]] = {
    "tiles" : {
    # Ground
        5: {"solidness": dict(top=True, right=True, bottom=True, left=True)},   
        6: {"solidness": dict(top=True, right=True, bottom=True, left=True)}, 
        7: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        8: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        17: {"solidness": dict(top=True, right=True, bottom=True, left=True)},  
        18: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        28: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        77: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        78: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        79: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
    },
    "tiles3" : {
    # Ground
        0: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        1: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        2: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        3: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        6: {"solidness": dict(top=True, right=True, bottom=True, left=True)}, 
        7: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        18: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        8: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        20: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        24: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        30: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        33: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        34: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
        35: {"solidness": dict(top=True, right=True, bottom=True, left=True)},
    },
}
