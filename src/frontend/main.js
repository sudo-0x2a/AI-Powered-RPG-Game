import { GAME_CONFIG } from './config.js';
import { GameScene } from './scenes.js';

const config = {
    ...GAME_CONFIG,
    scene: GameScene
};

const game = new Phaser.Game(config);

window.addEventListener('error', (event) => {
    console.error('Game Error:', event.error);
});


