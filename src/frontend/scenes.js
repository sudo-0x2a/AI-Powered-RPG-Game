import { ASSET_KEYS, ASSET_PATHS, TILESET_MAPPING } from './config.js';
import { InventoryUI, ChatUI } from './ui.js';

export class GameScene extends Phaser.Scene {
    constructor() {
        super({ key: 'GameScene' });
        this.player = null;
        this.cursors = null;
        this.npcs = [];
        this.gameData = null;
        this.inventoryUI = null;
        this.npcActionMenu = null;
        this.npcActionBackdrop = null;
        this.characterInfoPopup = null;
        this.characterInfoBackdrop = null;
    }

    preload() {
        this.load.image(ASSET_KEYS.world.image, ASSET_PATHS.world.image);
        this.load.tilemapTiledJSON(ASSET_KEYS.world.map, ASSET_PATHS.world.map);
        this.load.image(ASSET_KEYS.tiles.base, ASSET_PATHS.tiles.base);
        this.load.image(ASSET_KEYS.tiles.grass, ASSET_PATHS.tiles.grass);
        this.load.image(ASSET_KEYS.tiles.water, ASSET_PATHS.tiles.water);
        this.load.image(ASSET_KEYS.tiles.waterfall, ASSET_PATHS.tiles.waterfall);
        this.load.image(ASSET_KEYS.tiles.flower, ASSET_PATHS.tiles.flower);
        this.load.spritesheet(ASSET_KEYS.characters.player, ASSET_PATHS.characters.player, { frameWidth: 32, frameHeight: 32 });
        this.load.spritesheet(ASSET_KEYS.characters.merchant, ASSET_PATHS.characters.merchant, { frameWidth: 32, frameHeight: 32 });
        this.load.image(ASSET_KEYS.characters.knight, ASSET_PATHS.characters.knight);
        this.load.image(ASSET_KEYS.characters.npc, ASSET_PATHS.characters.npc);
        this.load.spritesheet(ASSET_KEYS.items.icons, ASSET_PATHS.items.icons, { frameWidth: 32, frameHeight: 32 });
        this.load.on('complete', async () => {
            try {
                this.gameData = await this.loadGameData();
            } catch (error) {
                this.gameData = {
                    map: { tile_size: 32, map_size: { width: 60, height: 60 } },
                    player: { id: 100, name: "Player", position: { x: 960, y: 960 }, stats: { Level: 1, Health: 100 } },
                    characters: { npcs: [{ id: 101, name: "Steve", role: "Merchant", position: { x: 800, y: 800 }, stats: { Relationship: 0.0 } }] }
                };
            }
        });
    }

    async loadGameData() {
        const mapResponse = await fetch('/api/map');
        const mapData = await mapResponse.json();
        const playerResponse = await fetch('/api/player');
        const playerData = await playerResponse.json();
        const charactersResponse = await fetch('/api/characters');
        const charactersData = await charactersResponse.json();
        return { map: mapData, player: playerData, characters: charactersData };
    }

    create() {
        this.enableAudioOnUserGesture();
        this.createPlayerAnimations();
        if (this.gameData) {
            this.createWorld();
        } else {
            const checkData = () => {
                if (this.gameData) {
                    this.createWorld();
                } else {
                    this.time.delayedCall(100, checkData);
                }
            };
            checkData();
        }
    }

    enableAudioOnUserGesture() {
        const resume = () => {
            try {
                if (this.sound && this.sound.context && this.sound.context.state === 'suspended') {
                    this.sound.context.resume();
                }
                if (this.sound && typeof this.sound.unlock === 'function') {
                    this.sound.unlock();
                }
            } catch (e) {}
            if (this.input) {
                this.input.off('pointerdown', resume);
                if (this.input.keyboard && this.input.keyboard.off) {
                    this.input.keyboard.off('keydown', resume);
                }
            }
        };
        if (this.input) {
            this.input.once('pointerdown', resume);
            if (this.input.keyboard && this.input.keyboard.once) {
                this.input.keyboard.once('keydown', resume);
            }
        }
    }

    createPlayerAnimations() {
        this.anims.create({ key: 'player_walk_down', frames: this.anims.generateFrameNumbers('player_sprite', { start: 0, end: 2 }), frameRate: 8, repeat: -1 });
        this.anims.create({ key: 'player_walk_left', frames: this.anims.generateFrameNumbers('player_sprite', { start: 3, end: 5 }), frameRate: 8, repeat: -1 });
        this.anims.create({ key: 'player_walk_right', frames: this.anims.generateFrameNumbers('player_sprite', { start: 6, end: 8 }), frameRate: 8, repeat: -1 });
        this.anims.create({ key: 'player_walk_up', frames: this.anims.generateFrameNumbers('player_sprite', { start: 9, end: 11 }), frameRate: 8, repeat: -1 });
        this.anims.create({ key: 'player_idle_down', frames: [{ key: 'player_sprite', frame: 1 }], frameRate: 1 });
        this.anims.create({ key: 'player_idle_left', frames: [{ key: 'player_sprite', frame: 4 }], frameRate: 1 });
        this.anims.create({ key: 'player_idle_right', frames: [{ key: 'player_sprite', frame: 7 }], frameRate: 1 });
        this.anims.create({ key: 'player_idle_up', frames: [{ key: 'player_sprite', frame: 10 }], frameRate: 1 });
    }

    createWorld() {
        try {
            this.map = this.make.tilemap({ key: ASSET_KEYS.world.map });
            const tilesets = [];
            this.map.tilesets.forEach(tileset => {
                const imageKey = TILESET_MAPPING[tileset.name];
                if (imageKey) {
                    const mappedTileset = this.map.addTilesetImage(tileset.name, imageKey);
                    if (mappedTileset) tilesets.push(mappedTileset);
                }
            });
            this.layers = {};
            const layerOrder = ['ground','water','water_grass','grass','farm','building','farm_up','building_up','tree'];
            layerOrder.forEach(layerName => {
                const layerData = this.map.layers.find(layer => layer.name === layerName);
                if (layerData) {
                    const layer = this.map.createLayer(layerName, tilesets);
                    if (layer) {
                        this.layers[layerName] = layer;
                        if (layerName === 'water') {
                            layer.setCollisionByExclusion([-1, 0]);
                            this.waterLayer = layer;
                        }
                    }
                }
            });
            if (this.map.widthInPixels && this.map.heightInPixels) {
                this.physics.world.setBounds(0, 0, this.map.widthInPixels, this.map.heightInPixels);
            }
            this.processBridgeOverrides();
            const worldWidth = this.map.widthInPixels || 1920;
            const worldHeight = this.map.heightInPixels || 1920;
            this.createFallbackCollision(worldWidth, worldHeight);
        } catch (error) {
            this.createFallbackWorldImage();
        }
        this.finishWorldCreation();
    }

    processBridgeOverrides() {
        const enableBridgeDetection = true;
        if (!enableBridgeDetection || !this.waterLayer || !this.layers) return;
        const bridgeLayers = ['building', 'building_up'].filter(name => this.layers[name]);
        for (let x = 0; x < this.map.width; x++) {
            for (let y = 0; y < this.map.height; y++) {
                const waterTile = this.waterLayer.getTileAt(x, y);
                if (waterTile && waterTile.index > 0) {
                    let hasBridge = false;
                    for (const layerName of bridgeLayers) {
                        const tile = this.layers[layerName].getTileAt(x, y);
                        if (tile && tile.index > 0) { hasBridge = true; break; }
                    }
                    if (hasBridge) { waterTile.setCollision(false); }
                }
            }
        }
    }

    finishWorldCreation() {
        this.createPlayer();
        this.setupCollisions();
        this.createNPCs();
        this.setupCamera();
        this.setupControls();
        this.createUI();
    }

    createFallbackWorldImage() {
        const bg = this.add.image(0, 0, ASSET_KEYS.world.image).setOrigin(0, 0);
        const width = bg.width || 1920;
        const height = bg.height || 1920;
        this.physics.world.setBounds(0, 0, width, height);
        this.createFallbackCollision(width, height);
    }

    createFallbackCollision(worldWidth, worldHeight) {
        const wallThickness = 32;
        const topWall = this.physics.add.staticGroup();
        topWall.create(worldWidth/2, -wallThickness/2, null).setSize(worldWidth, wallThickness).setVisible(false);
        const bottomWall = this.physics.add.staticGroup();
        bottomWall.create(worldWidth/2, worldHeight + wallThickness/2, null).setSize(worldWidth, wallThickness).setVisible(false);
        const leftWall = this.physics.add.staticGroup();
        leftWall.create(-wallThickness/2, worldHeight/2, null).setSize(wallThickness, worldHeight).setVisible(false);
        const rightWall = this.physics.add.staticGroup();
        rightWall.create(worldWidth + wallThickness/2, worldHeight/2, null).setSize(wallThickness, worldHeight).setVisible(false);
        this.fallbackCollisionGroups = [topWall, bottomWall, leftWall, rightWall];
    }

    createPlayer() {
        const playerData = this.gameData.player;
        const spriteKey = this.getSpriteKeyFromPath(playerData.sprite) || 'player_sprite';
        this.player = this.physics.add.sprite(playerData.position.x, playerData.position.y, spriteKey);
        this.player.setCollideWorldBounds(true);
        const scale = playerData.scale || 1.0;
        this.player.setScale(scale);
        this.player.gameData = playerData;
        this.player.currentDirection = 'down';
        const idleAnimation = playerData.animations?.idle || 'player_idle_down';
        if (this.anims.exists(idleAnimation)) { this.player.play(idleAnimation); } else { this.player.play('player_idle_down'); }
    }

    setupCollisions() {
        if (!this.player) { return; }
        let collisionsSet = 0;
        if (this.layers && this.layers['water']) {
            this.physics.add.collider(this.player, this.layers['water']);
            collisionsSet++;
        }
        if (this.fallbackCollisionGroups) {
            this.fallbackCollisionGroups.forEach(group => { this.physics.add.collider(this.player, group); collisionsSet++; });
        } else {
            const worldBounds = this.physics.world.bounds;
            this.createFallbackCollision(worldBounds.width, worldBounds.height);
            if (this.fallbackCollisionGroups) {
                this.fallbackCollisionGroups.forEach(group => { this.physics.add.collider(this.player, group); collisionsSet++; });
            }
        }
    }

    createNPCs() {
        this.npcs = [];
        if (this.gameData.characters && this.gameData.characters.npcs) {
            this.gameData.characters.npcs.forEach(npcData => {
                const spriteKey = this.getSpriteKeyFromPath(npcData.sprite) || 'npc_sprite';
                const npc = this.physics.add.sprite(npcData.position.x, npcData.position.y, spriteKey);
                npc.setCollideWorldBounds(true);
                npc.setScale(npcData.scale || 1.0);
                npc.gameData = npcData;
                if (npcData.role === 'Merchant') { npc.setFrame(1); }
                npc.setInteractive();
                npc.on('pointerdown', (pointer, localX, localY, event) => {
                    if (pointer.leftButtonDown()) {
                        const worldPoint = pointer.positionToCamera(this.cameras.main);
                        this.showNpcActionMenuAt(worldPoint.x, worldPoint.y, npcData);
                        this.faceNPCTowardsPlayer(npc);
                    }
                    event && event.stopPropagation && event.stopPropagation();
                });
                this.npcs.push(npc);
            });
        }
    }

    getSpriteKeyFromPath(spritePath) {
        if (!spritePath) return null;
        const filename = spritePath.split('/').pop();
        const nameWithoutExt = filename.split('.')[0];
        const spriteMap = { 'player': 'player_sprite', 'merchant': 'merchant_sprite', 'knight': 'knight_sprite', 'npc_2': 'npc_sprite' };
        return spriteMap[nameWithoutExt] || 'npc_sprite';
    }

    faceNPCTowardsPlayer(npc) {
        if (!this.player) return;
        const deltaX = this.player.x - npc.x;
        const deltaY = this.player.y - npc.y;
        const absDeltaX = Math.abs(deltaX);
        const absDeltaY = Math.abs(deltaY);
        if (absDeltaX > absDeltaY) {
            if (deltaX > 0) { npc.setFrame(7); } else { npc.setFrame(4); }
        } else {
            if (deltaY > 0) { npc.setFrame(1); } else { npc.setFrame(10); }
        }
    }

    showNpcActionMenuAt(worldX, worldY, npcData) {
        this.closeNpcActionMenu();
        this.closeCharacterInfoWindow();
        this.npcActionBackdrop = this.add.rectangle(this.cameras.main.scrollX + this.cameras.main.width / 2, this.cameras.main.scrollY + this.cameras.main.height / 2, this.cameras.main.width, this.cameras.main.height, 0x000000, 0.001)
            .setDepth(9000)
            .setInteractive()
            .on('pointerdown', () => this.closeNpcActionMenu());
        const width = 120; const height = 80; const margin = 8;
        const minX = this.cameras.main.scrollX + margin;
        const minY = this.cameras.main.scrollY + margin;
        const maxX = this.cameras.main.scrollX + this.cameras.main.width - width - margin;
        const maxY = this.cameras.main.scrollY + this.cameras.main.height - height - margin;
        const x = Math.min(Math.max(worldX, minX), maxX);
        const y = Math.min(Math.max(worldY, minY), maxY);
        const panel = this.add.rectangle(x, y, width, height, 0x1f2a36, 0.98).setStrokeStyle(2, 0x4b6378).setDepth(9001).setOrigin(0, 0.5);
        const title = this.add.text(x + 8, y - height/2 + 6, 'Actions', { fontSize: '12px', fill: '#ecf0f1', fontFamily: 'Arial', fontStyle: 'bold' }).setDepth(9002);
        const talkBtn = this.add.text(x + 8, y - 6, 'Talk', { fontSize: '12px', fill: '#3498db', fontFamily: 'Arial' }).setDepth(9002)
          .setInteractive({ useHandCursor: true })
          .on('pointerdown', () => {
              if (!this.chatUI) { this.chatUI = new ChatUI(this); }
              this.chatUI.open(npcData);
              this.closeNpcActionMenu();
          });
        const inspectBtn = this.add.text(x + 8, y + 14, 'Inspect', { fontSize: '12px', fill: '#2ecc71', fontFamily: 'Arial' }).setDepth(9002)
          .setInteractive({ useHandCursor: true })
          .on('pointerdown', () => { this.showCharacterInfoWindow(npcData); this.closeNpcActionMenu(); });
        this.npcActionMenu = { panel, title, talkBtn, inspectBtn };
    }

    closeNpcActionMenu() {
        if (this.npcActionMenu) {
            this.npcActionMenu.panel.destroy();
            this.npcActionMenu.title.destroy();
            this.npcActionMenu.talkBtn.destroy();
            this.npcActionMenu.inspectBtn.destroy();
            this.npcActionMenu = null;
        }
        if (this.npcActionBackdrop) { this.npcActionBackdrop.destroy(); this.npcActionBackdrop = null; }
    }

    showCharacterInfoWindow(npcData) {
        this.closeCharacterInfoWindow();
        const stats = npcData.stats || {};
        const name = npcData.name || 'Unknown';
        const role = npcData.role || 'NPC';
        const lines = [ `${name} (${role})`, `Level: ${stats.Level ?? stats.level ?? 'N/A'}`, `Health: ${stats.Health ?? stats.health ?? 'N/A'}`, stats.Relationship !== undefined ? `Relationship: ${stats.Relationship}` : null ].filter(Boolean);
        this.characterInfoBackdrop = this.add.rectangle(this.cameras.main.scrollX + this.cameras.main.width / 2, this.cameras.main.scrollY + this.cameras.main.height / 2, this.cameras.main.width, this.cameras.main.height, 0x000000, 0.001)
         .setDepth(9100).setInteractive().on('pointerdown', () => this.closeCharacterInfoWindow());
        const padding = 12; const width = 240; const lineHeight = 18; const height = padding * 2 + lines.length * lineHeight + 16;
        const x = this.cameras.main.scrollX + this.cameras.main.width / 2; const y = this.cameras.main.scrollY + this.cameras.main.height / 2;
        const bg = this.add.rectangle(x, y, width, height, 0x1f2a36, 0.98).setStrokeStyle(2, 0x4b6378).setDepth(9101);
        const title = this.add.text(x, y - height/2 + padding + 4, `${name}`, { fontSize: '16px', fill: '#ecf0f1', fontFamily: 'Arial', fontStyle: 'bold' }).setOrigin(0.5, 0).setDepth(9102);
        const details = this.add.text(x - width/2 + padding, y - height/2 + padding + 26, lines.slice(1).join('\n'), { fontSize: '13px', fill: '#bdc3c7', fontFamily: 'Arial', wordWrap: { width: width - padding * 2 } }).setDepth(9102);
        this.characterInfoPopup = { bg, title, details };
    }

    closeCharacterInfoWindow() {
        if (this.characterInfoPopup) {
            this.characterInfoPopup.bg.destroy();
            this.characterInfoPopup.title.destroy();
            this.characterInfoPopup.details.destroy();
            this.characterInfoPopup = null;
        }
        if (this.characterInfoBackdrop) { this.characterInfoBackdrop.destroy(); this.characterInfoBackdrop = null; }
    }

    setupCamera() {
        this.cameras.main.startFollow(this.player);
        if (this.map && this.map.widthInPixels) {
            this.cameras.main.setBounds(0, 0, this.map.widthInPixels, this.map.heightInPixels);
        } else {
            this.cameras.main.setBounds(0, 0, this.physics.world.bounds.width, this.physics.world.bounds.height);
        }
        this.cameras.main.setZoom(1.0);
    }

    setupControls() {
        this.cursors = this.input.keyboard.createCursorKeys();
        this.wasd = this.input.keyboard.addKeys('W,S,A,D');
        this.inventoryKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.I);
        this.input.keyboard.on('keydown-I', (event) => { if (this.chatUI && this.chatUI.isOpen) { event.stopPropagation(); } });
        this.escKey = this.input.keyboard.addKey(Phaser.Input.Keyboard.KeyCodes.ESC);
        this.escKey.on('down', () => {
            if (this.chatUI && this.chatUI.isOpen) { this.chatUI.close(); }
            if (this.npcActionMenu) { this.closeNpcActionMenu(); }
            if (this.inventoryUI && this.inventoryUI.isOpen) { this.inventoryUI.close(); }
        });
    }

    createUI() {
        if (this.player) {
            this.coordinateText = this.add.text(10, 40, `X: ${Math.round(this.player.x)}, Y: ${Math.round(this.player.y)}`, { fontSize: '12px', fill: '#ffffff', fontFamily: 'Arial', stroke: '#000000', strokeThickness: 2, backgroundColor: 'rgba(0, 0, 0, 0.5)', padding: { x: 5, y: 5 } }).setScrollFactor(0).setDepth(10000);
        }
        this.inventoryUI = new InventoryUI(this);
        this.inventoryInstructionText = this.add.text(10, 10, 'Press I to open Inventory', { fontSize: '12px', fill: '#ffffff', fontFamily: 'Arial', stroke: '#000000', strokeThickness: 2, backgroundColor: 'rgba(0, 0, 0, 0.5)', padding: { x: 5, y: 5 } }).setScrollFactor(0).setDepth(10000);
    }

    update() {
        if (this.inventoryKey && Phaser.Input.Keyboard.JustDown(this.inventoryKey)) {
            if (this.inventoryUI) { this.inventoryUI.toggle(); }
        }
        if (this.player && (!this.inventoryUI || !this.inventoryUI.isOpen) && (!this.chatUI || !this.chatUI.isOpen)) {
            const speed = 200;
            let isMoving = false;
            let newDirection = this.player.currentDirection;
            this.player.setVelocity(0);
            if (this.cursors.up.isDown || this.wasd.W.isDown) { this.player.setVelocityY(-speed); newDirection = 'up'; isMoving = true; }
            else if (this.cursors.down.isDown || this.wasd.S.isDown) { this.player.setVelocityY(speed); newDirection = 'down'; isMoving = true; }
            if (this.cursors.left.isDown || this.wasd.A.isDown) { this.player.setVelocityX(-speed); if (!isMoving) { newDirection = 'left'; } isMoving = true; }
            else if (this.cursors.right.isDown || this.wasd.D.isDown) { this.player.setVelocityX(speed); if (!isMoving) { newDirection = 'right'; } isMoving = true; }
            if (isMoving) {
                if (newDirection !== this.player.currentDirection || this.player.anims.currentAnim.key.includes('idle')) {
                    this.player.play(`player_walk_${newDirection}`);
                    this.player.currentDirection = newDirection;
                }
            } else {
                if (!this.player.anims.currentAnim.key.includes('idle')) {
                    this.player.play(`player_idle_${this.player.currentDirection}`);
                }
            }
            if (this.coordinateText) { this.coordinateText.setText(`X: ${Math.round(this.player.x)}, Y: ${Math.round(this.player.y)}`); }
        }
    }
}


