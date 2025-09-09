// Frontend configuration and constants

export const GAME_CONFIG = {
    type: Phaser.AUTO,
    width: 1024,
    height: 768,
    parent: 'game-container',
    backgroundColor: '#2c3e50',
    physics: {
        default: 'arcade',
        arcade: {
            gravity: { y: 0 },
            debug: false
        }
    },
    dom: {
        createContainer: true
    }
};

export const ASSET_KEYS = {
    world: {
        image: 'worldmap_image',
        map: 'worldmap'
    },
    tiles: {
        base: 'base_tiles',
        grass: 'grass_tiles',
        water: 'water_tiles',
        waterfall: 'waterfall_tiles',
        flower: 'flower_tiles'
    },
    characters: {
        player: 'player_sprite',
        merchant: 'merchant_sprite',
        knight: 'knight_sprite',
        npc: 'npc_sprite'
    },
    items: {
        icons: 'item_icons'
    }
};

export const ASSET_PATHS = {
    world: {
        image: 'assets/map/world_map.png',
        map: 'assets/map/world_map.json'
    },
    tiles: {
        base: 'assets/map/[Base]BaseChip_pipo.png',
        grass: 'assets/map/[A]Grass_pipo.png',
        water: 'assets/map/[A]Water_pipo.png',
        waterfall: 'assets/map/[A]WaterFall_pipo.png',
        flower: 'assets/map/[A]Flower_pipo.png'
    },
    characters: {
        player: 'assets/characters/player.png',
        merchant: 'assets/characters/merchant.png',
        knight: 'assets/characters/knight.png',
        npc: 'assets/characters/npc_2.png'
    },
    items: {
        icons: 'assets/items/items_icon.png'
    }
};

export const KEYBINDS = {
    inventory: 'I',
    wasd: 'W,S,A,D'
};

export const TILESET_MAPPING = {
    '[Base]BaseChip_pipo': ASSET_KEYS.tiles.base,
    '[A]Grass_pipo': ASSET_KEYS.tiles.grass,
    '[A]Water_pipo': ASSET_KEYS.tiles.water,
    '[A]WaterFall_pipo': ASSET_KEYS.tiles.waterfall,
    '[A]Flower_pipo': ASSET_KEYS.tiles.flower
};


