// UI module: InventoryUI and ChatUI

export class InventoryUI {
    constructor(scene) {
        this.scene = scene;
        this.isOpen = false;
        this.itemSlots = [];
        this.playerInventory = [];
        this.slotSize = 64;
        this.padding = 8;
        this.slotsPerRow = 8;
        this.maxSlots = 32;
        this.iconFrameWidth = 32;
        this.iconFrameHeight = 32;
        this._cachedSheetColumns = null;
        this.infoPopup = null;
        this.infoBackdrop = null;
        this.createUI();
    }

    createUI() {
        const panelWidth = (this.slotsPerRow * this.slotSize) + ((this.slotsPerRow + 1) * this.padding);
        const panelHeight = (Math.ceil(this.maxSlots / this.slotsPerRow) * this.slotSize) + ((Math.ceil(this.maxSlots / this.slotsPerRow) + 1) * this.padding) + 60;
        const centerX = this.scene.cameras.main.width / 2;
        const centerY = this.scene.cameras.main.height / 2;
        this.backgroundPanel = this.scene.add.rectangle(centerX, centerY, panelWidth, panelHeight, 0x2c3e50, 0.95)
            .setStrokeStyle(2, 0x34495e)
            .setScrollFactor(0)
            .setDepth(1000)
            .setVisible(false);
        this.titleText = this.scene.add.text(centerX, centerY - panelHeight/2 + 30, 'INVENTORY', { fontSize: '20px', fill: '#ecf0f1', fontFamily: 'Arial', fontStyle: 'bold' })
            .setOrigin(0.5)
            .setScrollFactor(0)
            .setDepth(1001)
            .setVisible(false);
        this.closeText = this.scene.add.text(centerX, centerY + panelHeight/2-300, 'Press I to close', { fontSize: '14px', fill: '#bdc3c7', fontFamily: 'Arial' })
            .setOrigin(0.5)
            .setScrollFactor(0)
            .setDepth(1001)
            .setVisible(false);
        this.createItemSlots(centerX, centerY, panelWidth, panelHeight);
    }

    createItemSlots(centerX, centerY, panelWidth, panelHeight) {
        const startX = centerX - (panelWidth / 2) + this.padding + (this.slotSize / 2);
        const startY = centerY - (panelHeight / 2) + 60 + this.padding + (this.slotSize / 2);
        for (let i = 0; i < this.maxSlots; i++) {
            const row = Math.floor(i / this.slotsPerRow);
            const col = i % this.slotsPerRow;
            const x = startX + col * (this.slotSize + this.padding);
            const y = startY + row * (this.slotSize + this.padding);
            const slotBg = this.scene.add.rectangle(x, y, this.slotSize - 4, this.slotSize - 4, 0x34495e)
                .setStrokeStyle(1, 0x7f8c8d)
                .setScrollFactor(0)
                .setDepth(1001)
                .setVisible(false);
            const itemIcon = this.scene.add.image(x, y, 'item_icons', 0)
                .setScale(Math.min((this.slotSize - 8) / this.iconFrameWidth, (this.slotSize - 8) / this.iconFrameHeight))
                .setScrollFactor(0)
                .setDepth(1002)
                .setVisible(false);
            itemIcon.setInteractive({ useHandCursor: true });
            itemIcon.on('pointerdown', (pointer) => {
                if (pointer.leftButtonDown()) {
                    this.showItemInfoAt(itemIcon.x, itemIcon.y, slot.itemData);
                }
            });
            const quantityText = this.scene.add.text(x + (this.slotSize / 2) - 8, y + (this.slotSize / 2) - 8, '', { fontSize: '12px', fill: '#f1c40f', fontFamily: 'Arial', fontStyle: 'bold', stroke: '#2c3e50', strokeThickness: 2 })
                .setOrigin(1, 1)
                .setScrollFactor(0)
                .setDepth(1003)
                .setVisible(false);
            const slot = { background: slotBg, icon: itemIcon, quantity: quantityText, isEmpty: true, itemData: null };
            this.itemSlots.push(slot);
        }
    }

    async fetchPlayerInventory() {
        try {
            const response = await fetch('/api/player');
            const playerData = await response.json();
            this.playerInventory = playerData.inventory || [];
            return this.playerInventory;
        } catch (error) {
            console.error('Error fetching player inventory:', error);
            return [];
        }
    }

    updateDisplay() {
        this.itemSlots.forEach(slot => {
            slot.isEmpty = true;
            slot.itemData = null;
            slot.icon.setVisible(false);
            slot.quantity.setVisible(false);
            slot.quantity.setText('');
        });
        this.playerInventory.forEach((item, index) => {
            if (index < this.maxSlots && item.Quantity > 0) {
                const slot = this.itemSlots[index];
                const iconPos = item.icon_pos || item.IconPos;
                const frameIndex = this.getFrameIndex(iconPos);
                slot.isEmpty = false;
                slot.itemData = item;
                slot.icon.setFrame(frameIndex);
                slot.icon.setVisible(this.isOpen);
                if (item.Quantity > 1) {
                    slot.quantity.setText(item.Quantity.toString());
                    slot.quantity.setVisible(this.isOpen);
                }
            }
        });
    }

    getFrameIndex(iconPos) {
        if (!iconPos || iconPos.length < 2) {
            return 0;
        }
        const columns = this.getSpritesheetColumns();
        const x = Math.max(0, Math.floor(iconPos[0]));
        const y = Math.max(0, Math.floor(iconPos[1]));
        return (y * columns) + x;
    }

    getSpritesheetColumns() {
        if (this._cachedSheetColumns) return this._cachedSheetColumns;
        try {
            const tex = this.scene.textures.get('item_icons');
            const img = tex && tex.getSourceImage ? tex.getSourceImage() : null;
            if (img && img.width) {
                this._cachedSheetColumns = Math.max(1, Math.floor(img.width / this.iconFrameWidth));
            } else {
                this._cachedSheetColumns = 32;
            }
        } catch (e) {
            this._cachedSheetColumns = 32;
        }
        return this._cachedSheetColumns;
    }

    showItemInfoAt(x, y, itemData) {
        if (!this.isOpen || !itemData) return;
        this.closeItemInfo();
        this.infoBackdrop = this.scene.add.rectangle(this.scene.cameras.main.width / 2, this.scene.cameras.main.height / 2, this.scene.cameras.main.width, this.scene.cameras.main.height, 0x000000, 0.001)
            .setScrollFactor(0)
            .setDepth(1100)
            .setInteractive()
            .on('pointerdown', () => this.closeItemInfo())
            .setVisible(true);
        const name = itemData.Name || itemData.name || 'Unknown Item';
        const type = itemData.Type || itemData.type || 'Unknown';
        const tradable = (itemData.Tradable !== undefined ? itemData.Tradable : itemData.tradable) ? 'Yes' : 'No';
        const description = itemData.Description || itemData.description || '';
        const price = itemData.Price !== undefined ? itemData.Price : itemData.price;
        const effect = itemData.Effect || itemData.effect || {};
        const quantity = itemData.Quantity !== undefined ? itemData.Quantity : itemData.quantity || 0;
        const effectStr = typeof effect === 'object' ? Object.entries(effect).filter(([k, v]) => v && v !== 0 && k !== 'None').map(([k, v]) => `${k}: +${v}`).join(', ') : String(effect);
        const lines = [name, `Type: ${type}`, `Tradable: ${tradable}`, `Price: ${price} gold`, `Quantity: ${quantity}`, effectStr ? `Effect: ${effectStr}` : null, '', description].filter(Boolean);
        const padding = 10;
        const width = 200;
        const lineHeight = 18;
        const height = padding * 2 + lines.length * lineHeight + 16;
        const screenW = this.scene.cameras.main.width;
        const screenH = this.scene.cameras.main.height;
        let px = Math.min(Math.max(x + 40, width / 2 + 10), screenW - width / 2 - 10);
        let py = Math.min(Math.max(y, height / 2 + 10), screenH - height / 2 - 10);
        const bg = this.scene.add.rectangle(px, py, width, height, 0x1f2a36, 0.98)
            .setStrokeStyle(2, 0x4b6378)
            .setScrollFactor(0)
            .setDepth(1101)
            .setVisible(true);
        const title = this.scene.add.text(px, py - height/2 + padding + 4, name, { fontSize: '16px', fill: '#ecf0f1', fontFamily: 'Arial', fontStyle: 'bold' })
            .setOrigin(0.5, 0)
            .setScrollFactor(0)
            .setDepth(1102)
            .setVisible(true);
        const details = this.scene.add.text(px - width/2 + padding, py - height/2 + padding + 26, lines.slice(1).join('\n'), { fontSize: '13px', fill: '#bdc3c7', fontFamily: 'Arial', wordWrap: { width: width - padding * 2 } })
            .setScrollFactor(0)
            .setDepth(1102)
            .setVisible(true);
        this.infoPopup = { bg, title, details };
    }

    closeItemInfo() {
        if (this.infoPopup) {
            this.infoPopup.bg.destroy();
            this.infoPopup.title.destroy();
            this.infoPopup.details.destroy();
            this.infoPopup = null;
        }
        if (this.infoBackdrop) {
            this.infoBackdrop.destroy();
            this.infoBackdrop = null;
        }
    }

    async toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            await this.open();
        }
    }

    async open() {
        if (this.isOpen) return;
        this.isOpen = true;
        await this.fetchPlayerInventory();
        this.backgroundPanel.setVisible(true);
        this.titleText.setVisible(true);
        this.closeText.setVisible(true);
        this.itemSlots.forEach(slot => { slot.background.setVisible(true); });
        this.updateDisplay();
        if (this.scene.player) {
            this.scene.player.setVelocity(0);
        }
    }

    close() {
        if (!this.isOpen) return;
        this.isOpen = false;
        this.backgroundPanel.setVisible(false);
        this.titleText.setVisible(false);
        this.closeText.setVisible(false);
        this.itemSlots.forEach(slot => { slot.background.setVisible(false); slot.icon.setVisible(false); slot.quantity.setVisible(false); });
    }
}

export class ChatUI {
  constructor(scene) {
    this.scene = scene;
    this.isOpen = false;
    this.currentNpc = null;
    this.components = null;
    this.messagesContainer = null;
    this.messagesMask = null;
    this.messages = [];
    this.viewport = { x: 0, y: 0, width: 0, height: 0 };
    this.scrollY = 0;
    this.maxScroll = 0;
    this.domInput = null;
    this.historyByNpc = {};
    this._lastNpcId = null;
  }

  createBaseUI() {
    const width = 600;
    const height = 380;
    const x = this.scene.cameras.main.width / 2;
    const y = this.scene.cameras.main.height - (height / 2) - 180;
    const panel = this.scene.add.rectangle(x, y, width, height, 0x1f2a36, 0.98)
    .setStrokeStyle(2, 0x4b6378)
    .setScrollFactor(0)
    .setDepth(10050)
    .setVisible(false);
    const title = this.scene.add.text(x - width/2 + 12, y - height/2 + 12, 'Chat', { fontSize: '16px', fill: '#ecf0f1', fontFamily: 'Arial', fontStyle: 'bold' })
    .setScrollFactor(0)
    .setDepth(10051)
    .setVisible(false);
    const closeHint = this.scene.add.text(x + width/2 - 12, y - height/2 + 12, 'ESC to close', { fontSize: '12px', fill: '#bdc3c7', fontFamily: 'Arial' })
    .setOrigin(1, 0)
    .setScrollFactor(0)
    .setDepth(10051)
    .setVisible(false);
    const viewportPadding = 10;
    const viewportX = x - width/2 + viewportPadding;
    const viewportY = y - height/2 + 40;
    const viewportW = width - viewportPadding * 2;
    const viewportH = height - 40 - 64;
    const viewportBg = this.scene.add.rectangle(viewportX + viewportW/2, viewportY + viewportH/2, viewportW, viewportH, 0x243647, 0.9)
    .setStrokeStyle(1, 0x3d566e)
    .setScrollFactor(0)
    .setDepth(10051)
    .setVisible(false)
    .setInteractive();
    const container = this.scene.add.container(viewportX, viewportY)
      .setScrollFactor(0)
      .setDepth(10052)
      .setVisible(false);
    const shape = this.scene.add.graphics({ x: viewportX, y: viewportY });
    shape.fillStyle(0xffffff);
    shape.fillRect(0, 0, viewportW, viewportH);
    shape.setScrollFactor(0);
    const mask = shape.createGeometryMask();
    container.setMask(mask);
    shape.setVisible(false);
    const inputY = y + height/2 - 30;
    const html = `\n      <div style="display:flex; gap:8px; width:${viewportW}px;">\n        <input id="chatInput" type="text" placeholder="Type a message..." \n               style="flex:1; padding:8px 10px; font-size:14px; border-radius:4px; border:1px solid #4b6378; background:#15222e; color:#ecf0f1; outline:none;" />\n        <button id="chatSend" style="padding:8px 14px; font-size:14px; border-radius:4px; border:1px solid #4b6378; background:#2e86de; color:#ecf0f1; cursor:pointer;">Send</button>\n      </div>`;
    const dom = this.scene.add.dom(viewportX + viewportW/2, inputY).createFromHTML(html)
      .setScrollFactor(0)
      .setDepth(10053)
      .setVisible(false);
    this.components = { panel, title, closeHint, viewportBg };
    this.messagesContainer = container;
    this.messagesMask = mask;
    this._messagesMaskShape = shape;
    this.viewport = { x: viewportX, y: viewportY, width: viewportW, height: viewportH };
    this.domInput = dom;
    this._wheelHandler = (pointer, gameObjects, deltaX, deltaY) => {
      if (!this.isOpen) return;
      const px = pointer.x;
      const py = pointer.y;
      const left = this.viewport.x;
      const top = this.viewport.y;
      const right = left + this.viewport.width;
      const bottom = top + this.viewport.height;
      if (px >= left && px <= right && py >= top && py <= bottom) {
        this.scrollBy(deltaY * 0.5);
      }
    };
  }

  open(npcData) {
    if (!this.components) {
      this.createBaseUI();
    }
    if (this.isOpen && this.currentNpc && this.currentNpc.id !== npcData.id) {
      this.requestSummary();
    }
    this.isOpen = true;
    this.currentNpc = npcData;
    this.scrollY = 0;
    this.maxScroll = 0;
    const { panel, title, closeHint, viewportBg } = this.components;
    panel.setVisible(true);
    title.setText(`Chat with ${npcData.name}`);
    title.setVisible(true);
    closeHint.setVisible(true);
    viewportBg.setVisible(true);
    this.messagesContainer.setVisible(true);
    this.domInput.setVisible(true);
    if (!this._messagesMaskShape) {
      const shape = this.scene.add.graphics({ x: this.viewport.x, y: this.viewport.y });
      shape.fillStyle(0xffffff);
      shape.fillRect(0, 0, this.viewport.width, this.viewport.height);
      shape.setScrollFactor(0);
      const mask = shape.createGeometryMask();
      this.messagesContainer.setMask(mask);
      shape.setVisible(false);
      this.messagesMask = mask;
      this._messagesMaskShape = shape;
    }
    const npcId = npcData.id;
    if (this._lastNpcId !== npcId) {
      this.messagesContainer.removeAll(true);
      const history = this.historyByNpc[npcId] || [];
      history.forEach(m => this._addMessageVisual(m.text, m.sender, true));
      this._lastNpcId = npcId;
      this.scrollBy(99999);
    }
    const root = this.domInput.getChildByID('chatInput');
    const sendBtn = this.domInput.getChildByID('chatSend');
    if (root && sendBtn) {
      root.value = '';
      const send = async () => {
        const text = root.value.trim();
        if (!text) return;
        root.value = '';
        await this.sendMessage(text);
      };
      this._keydownHandler = (e) => {
        const key = e.key;
        if (key === 'Enter') { e.preventDefault(); e.stopPropagation(); send(); return; }
        if (key === 'Escape') { e.preventDefault(); e.stopPropagation(); this.close(); return; }
        if (key === ' ' || key === 'Spacebar' || e.code === 'Space' || e.keyCode === 32) {
          e.preventDefault(); e.stopPropagation();
          const start = root.selectionStart || 0;
          const end = root.selectionEnd || 0;
          const val = root.value || '';
          root.value = val.slice(0, start) + ' ' + val.slice(end);
          const pos = start + 1;
          try { root.setSelectionRange(pos, pos); } catch (_) {}
          return;
        }
        const blockKeys = ['w','a','s','d','W','A','S','D','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','i','I'];
        if (blockKeys.includes(key)) { e.stopPropagation(); }
      };
      root.addEventListener('keydown', this._keydownHandler);
      this._clickHandler = () => send();
      sendBtn.addEventListener('click', this._clickHandler);
      setTimeout(() => root.focus(), 0);
    }
    if (!this._wheelBound) {
      this.scene.input.on('wheel', this._wheelHandler);
      this._wheelBound = true;
    }
  }

  close() {
    if (!this.isOpen) return;
    this.isOpen = false;
    const { panel, title, closeHint, viewportBg } = this.components || {};
    if (panel) panel.setVisible(false);
    if (title) title.setVisible(false);
    if (closeHint) closeHint.setVisible(false);
    if (viewportBg) viewportBg.setVisible(false);
    if (this.messagesContainer) this.messagesContainer.setVisible(false);
    if (this.domInput) this.domInput.setVisible(false);
    const root = this.domInput && this.domInput.getChildByID('chatInput');
    const sendBtn = this.domInput && this.domInput.getChildByID('chatSend');
    if (root && this._keydownHandler) root.removeEventListener('keydown', this._keydownHandler);
    if (sendBtn && this._clickHandler) sendBtn.removeEventListener('click', this._clickHandler);
    if (root) root.blur();
    this.requestSummary();
    if (this._messagesMaskShape) {
      this._messagesMaskShape.destroy();
      this._messagesMaskShape = null;
    }
  }

  requestSummary() {
    try {
      const npcId = (this.currentNpc && this.currentNpc.id) || this._lastNpcId || null;
      if (!npcId) { return; }
      const playerId = (this.scene.gameData && this.scene.gameData.player && this.scene.gameData.player.id) || null;
      fetch('/api/chat/close', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ npc_id: npcId, player_id: playerId }) })
      .then(resp => resp.json())
      .then(() => {})
      .catch(err => console.error('Summarization request failed:', err));
    } catch (e) {
      console.error('Error preparing summarization request:', e);
    }
  }

  scrollBy(delta) {
    const viewportH = this.viewport.height;
    const contentH = this._getContentHeight();
    this.maxScroll = Math.max(0, contentH - viewportH);
    this.scrollY = Phaser.Math.Clamp(this.scrollY + delta, 0, this.maxScroll);
    this.messagesContainer.y = this.viewport.y - this.scrollY;
  }

  _getContentHeight() {
    if (this.messagesContainer && this.messagesContainer.list.length > 0) {
      const last = this.messagesContainer.list[this.messagesContainer.list.length - 1];
      return last.y + last.height + 8;
    }
    return 0;
  }

  addMessage(text, sender) {
    const npcId = this.currentNpc ? this.currentNpc.id : null;
    if (npcId !== null) {
      if (!this.historyByNpc[npcId]) this.historyByNpc[npcId] = [];
      this.historyByNpc[npcId].push({ sender, text });
    }
    this._addMessageVisual(text, sender, false);
  }

  _addMessageVisual(text, sender) {
    const padding = 8;
    const innerWidth = this.viewport.width - padding * 2;
    const color = sender === 'player' ? '#ecf0f1' : '#a2d5f2';
    const alignRight = sender === 'player';
    let nextY = padding;
    if (this.messagesContainer.list.length > 0) {
      const last = this.messagesContainer.list[this.messagesContainer.list.length - 1];
      nextY = last.y + last.height + 6;
    }
    const textObj = this.scene.add.text(0, 0, text, { fontSize: '15px', fill: color, fontFamily: 'Arial', wordWrap: { width: innerWidth } }).setDepth(10052);
    this.messagesContainer.add(textObj);
    const localX = padding + (alignRight ? (innerWidth - textObj.width) : 0);
    const localY = nextY;
    textObj.x = localX;
    textObj.y = localY;
    this.scrollBy(99999);
  }

  async sendMessage(text) {
    this.addMessage(text, 'player');
    try {
      const resp = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ npc_id: this.currentNpc.id, message: text }) });
      const data = await resp.json();
      const reply = data && data.reply ? data.reply : '...';
      this.addMessage(reply, 'npc');
    } catch (e) {
      this.addMessage('Failed to reach the server. Please try again.', 'npc');
    }
  }
}


