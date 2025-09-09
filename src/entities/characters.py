import json
import os
from src.core.utilities import load_json_config
from .items import Item

class Character:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config_dir = os.path.dirname(config_path)
        self.config = load_json_config(config_path)
        self.id = self.config["id"]
        self.name = self.config["name"]
        self.role = self.config["role"]
        self.attributes = self.config["attributes"]
        self.inventory = self._load_inventory()
        
        # Load frontend configuration
        self.frontend_config = self.config.get("frontend_config", {})
        
        # Load gameplay configuration  
        self.gameplay_config = self.config.get("gameplay_config", {})

    def show_stats(self):
        stats = {
            "Name": self.name,
            "Role": self.role,
            "Level": self.attributes["level"],
            "Health": self.attributes["health"]
        }
        return stats

    def _load_item_data(self, item_name: str):
        """Initialize an item object from its JSON config file"""
        # Go up two levels from src/entities/ to reach config/items/
        items_dir = os.path.join(os.path.dirname(__file__), "..", "..", "config", "items")
        item_config_path = os.path.join(items_dir, f"{item_name}.json")
        
        if not os.path.exists(item_config_path):
            raise FileNotFoundError(f"Item config file not found: {item_config_path}")
        
        return Item(item_config_path)

    def _load_inventory(self):
        """Transform inventory data from character config to Item objects"""
        inventory = []
        
        if "inventory" in self.config and self.config["inventory"]:
            for item_entry in self.config["inventory"]:
                for item_name, quantity in item_entry.items():
                    try:
                        item = self._load_item_data(item_name)
                        item.set_quantity(quantity)
                        inventory.append(item)
                        
                    except FileNotFoundError as e:
                        print(f"Warning: {e}")
                        continue
                    except ValueError as e:
                        print(f"Warning: Invalid quantity for {item_name}: {e}")
                        continue
        return inventory

    def show_inventory(self):
        """Display detailed information about all items in the inventory"""
        inventory_info = []
        if not self.inventory:
            return "Inventory is empty."
        
        for item in self.inventory:
            inventory_info.append(item.show_info())
        
        return inventory_info


    def add_item(self, item: Item, quantity: int = 1, silent: bool = False):
        """
        Add an item to the inventory. If the item already exists, add to its quantity.
        If it doesn't exist, add a new item object with the correct quantity.
        
        Args:
            item: The Item object to add
            quantity: How many to add (default: 1)
            silent: If True, suppress print statements (default: False)
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        # Check if item already exists in inventory (by name)
        existing_item = None
        for inv_item in self.inventory:
            if inv_item.name == item.name:
                existing_item = inv_item
                break
        
        if existing_item:
            # Item exists, add to existing quantity
            existing_item.set_quantity(existing_item.quantity + quantity)
            if not silent:
                print(f"Added {quantity} {item.name}(s). Total: {existing_item.quantity}")
        else:
            # Item doesn't exist, create a new item object with correct quantity
            # Try to load the item from its config file using the same method as inventory loading
            try:
                new_item = self._load_item_data(item.name.replace(' ', '_'))
                new_item.set_quantity(quantity)
                self.inventory.append(new_item)
                if not silent:
                    print(f"Added {quantity} {item.name}(s) to inventory")
            except FileNotFoundError:
                # If we can't load from file, clone the existing item
                import copy
                new_item = copy.deepcopy(item)
                new_item.set_quantity(quantity)
                self.inventory.append(new_item)
                if not silent:
                    print(f"Added {quantity} {item.name}(s) to inventory (cloned)")

    def remove_item(self, item: Item, quantity: int = 1, silent: bool = False):
        """
        Remove an item from the inventory. If quantity reaches 0, remove the item object.
        
        Args:
            item: The Item object to remove (can match by name)
            quantity: How many to remove (default: 1)
            silent: If True, suppress print statements (default: False)
        
        Returns:
            bool: True if removal was successful, False if item not found or insufficient quantity
        """
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        # Find the item in inventory (by name)
        target_item = None
        for inv_item in self.inventory:
            if inv_item.name == item.name:
                target_item = inv_item
                break
        
        if not target_item:
            if not silent:
                print(f"Item '{item.name}' not found in inventory")
            return False
        
        if target_item.quantity < quantity:
            if not silent:
                print(f"Insufficient quantity. Have {target_item.quantity}, tried to remove {quantity}")
            return False
        
        # Update quantity
        new_quantity = target_item.quantity - quantity
        
        if new_quantity == 0:
            # Remove the item object completely
            self.inventory.remove(target_item)
            if not silent:
                print(f"Removed all {item.name}(s) from inventory")
        else:
            # Update the quantity
            target_item.set_quantity(new_quantity)
            if not silent:
                print(f"Removed {quantity} {item.name}(s). Remaining: {new_quantity}")
        
        return True
    
    def find_item_by_name(self, item_name: str):
        """
        Find an item in inventory by name.
        
        Args:
            item_name: Name of the item to find
            
        Returns:
            Item or None: The item if found, None otherwise
        """
        for item in self.inventory:
            if item.name.lower() == item_name.lower():
                return item
        return None
        
    def get_frontend_data(self):
        """Get all data needed for frontend rendering"""
        frontend_data = {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "stats": self.show_stats()
        }
        
        # Add frontend configuration
        frontend_data.update(self.frontend_config)
        
        # Ensure required fields have defaults
        if "sprite" not in frontend_data:
            # Default sprites based on role
            sprite_defaults = {
                "Merchant": "/assets/characters/merchant.png",
                "Warrior": "/assets/characters/player.png",
                "Player": "/assets/characters/player.png"
            }
            frontend_data["sprite"] = sprite_defaults.get(self.role, "/assets/characters/npc_2.png")
            
        if "position" not in frontend_data:
            # Default position
            frontend_data["position"] = {"x": 500, "y": 500}
            
        return frontend_data
        
    def get_api_data(self):
        """Get data for API responses"""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "stats": self.show_stats(),
            "frontend_config": self.frontend_config,
            "gameplay_config": self.gameplay_config
        }

class NPC(Character):
    def __init__(self, config_path: str):
        super().__init__(config_path)
        self.ai_agent_config = self.config["ai_agent_config"]

    def show_stats(self):
        stats = super().show_stats()
        stats["Relationship"] = self.attributes["relationship"]
        return stats


class Player(Character):
    def __init__(self, config_path: str):
        super().__init__(config_path)

