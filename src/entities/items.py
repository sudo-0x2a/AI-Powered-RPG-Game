import os
from src.core.utilities import load_json_config

class Item:
    def __init__(self, config_path: str):
        self.config = load_json_config(config_path)
        self.id = self.config["id"]
        self.name = self.config["name"]
        self.type = self.config["type"]
        self.tradable = self.config["tradable"]
        self.icon_pos = self.config["icon_pos"]
        self.description = self.config["description"]
        self.price = self.config["price"]
        self.effect = self.config["effect"]
        self.quantity = 0

    def show_info(self):
        info = {"ID": self.id, "Name": self.name, "Type": self.type, "Tradable": self.tradable, "Description": self.description, "Price": self.price, "Effect": self.effect, "Quantity": self.quantity, "icon_pos": self.icon_pos, "IconPos": self.icon_pos}
        return info

    def set_quantity(self, quantity: int):
        if quantity < 0:
            raise ValueError("Quantity cannot be negative")
        self.quantity = quantity

        