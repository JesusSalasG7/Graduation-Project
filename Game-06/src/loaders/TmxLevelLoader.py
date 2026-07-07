
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.Tilemap import Tilemap
import settings 


class TmxLevelLoader:
    FILE_EXT = "tmx"

    def __init__(self) -> None:
        self.height = None
        self.width = None
        self.tilewidth = None
        self.tileheight = None
        self.level = None
        self.first_ids = {}

    def load(self, level: Any, level_path: Path) -> None:
        tree = ET.parse(f"{level_path}.{self.FILE_EXT}")
        root = tree.getroot()
        self.level = f"level{level.num_level}"

        self.width = int(root.attrib["width"])
        self.height = int(root.attrib["height"])
        self.tilewidth = int(root.attrib["tilewidth"])
        self.tileheight = int(root.attrib["tileheight"])

        for tileset in root.findall("tileset"):
            name = Path(tileset.attrib["source"]).stem
            self.first_ids[name] = int(tileset.attrib["firstgid"])

        for group in root.findall("group"):
            group_name = group.attrib["name"]
            getattr(self, f"load_{group_name}")(level, group)

    def load_tilemap(self, level: Any, group: ET.Element) -> None:
        tilemap = Tilemap(self.height, self.width, self.tilewidth, self.tileheight)
        id_texturs = None

        for layer in group.findall("layer"):
            tilemap.create_layer()
            data = [
                line for line in layer.find("data").text.splitlines() if len(line) > 0
            ]
            for i in range(self.height):
                line = [s for s in data[i].split(",") if len(s) > 0]
                for j in range(self.width):
                    value = int(line[j])

                    if self.level in  settings.TILEMAP: 
                        for rango, textura in settings.TILEMAP[self.level].items():
                            if rango[0] <= value <= rango[1]:  # Si el valor está dentro del rango
                                id_texturs = textura 

                    frame_index = value - self.first_ids[id_texturs]
                    tilemap.set_new_tile(i, j, frame_index, id_texturs)

        level.tilemap = tilemap


    def load_traps(self, level: Any, group: ET.Element) -> None:
        
        for layer in group.findall("layer"):
            trap_name = layer.attrib["name"]
            data = [line for line in layer.find("data").text.splitlines() if len(line) > 0]
            for i in range(self.height):
                line = [s for s in data[i].split(",") if len(s) > 0]
                for j in range(self.width):
                    value = int(line[j])
                    
                    if value == 0:
                        continue

                    if self.level in  settings.TILEMAP: 
                        for rango, textura in settings.TILEMAP[self.level].items():
                            if rango[0] <= value <= rango[1]:  # Si el valor está dentro del rango
                                id_texturs = textura
                    
                    frame_index = value - self.first_ids[id_texturs]

                    level.add_trap(
                        {
                            "trap_name": trap_name,
                            "frame_index": frame_index,
                            "x": j * self.tilewidth,
                            "y": i * self.tileheight,
                            "width": self.tilewidth,
                            "height": self.tileheight,
                        }
                    )

    def load_items(self, level: Any, group: ET.Element) -> None:
        
        for layer in group.findall("layer"):
            item_name = layer.attrib["name"]
            data = [line for line in layer.find("data").text.splitlines() if len(line) > 0]
            for i in range(self.height):
                line = [s for s in data[i].split(",") if len(s) > 0]
                for j in range(self.width):
                    value = int(line[j])
                    
                    if value == 0:
                        continue

                    if self.level in  settings.TILEMAP: 
                        for rango, textura in settings.TILEMAP[self.level].items():
                            if rango[0] <= value <= rango[1]:  # Si el valor está dentro del rango
                                id_texturs = textura
                    
                    frame_index = value - self.first_ids[id_texturs]

                    level.add_item(
                        {
                            "item_name": item_name,
                            "frame_index": frame_index,
                            "x": j * self.tilewidth,
                            "y": i * self.tileheight,
                            "width": self.tilewidth,
                            "height": self.tileheight,
                        }
                    )

    def load_creatures(self, level: Any, group: ET.Element) -> None:
        layer = group.find("layer")
        data = [line for line in layer.find("data").text.splitlines() if len(line) > 0]
        for i in range(self.height):
            line = [s for s in data[i].split(",") if len(s) > 0]
            for j in range(self.width):
                value = int(line[j])

                if value == 0:
                    continue

                if self.level in  settings.TILEMAP: 
                        for rango, textura in settings.TILEMAP[self.level].items():
                            if rango[0] <= value <= rango[1]:  # Si el valor está dentro del rango
                                id_texturs = textura

                frame_index = value - self.first_ids[id_texturs]

                level.add_creature(
                    {
                        "tile_index": frame_index,
                        "x": j * self.tilewidth,
                        "y": i * self.tileheight,
                        "width": self.tilewidth,
                        "height": self.tileheight,
                    }
                )
