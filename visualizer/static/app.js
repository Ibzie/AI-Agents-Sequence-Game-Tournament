((global) => {
  'use strict';

  const BOARD_LAYOUT = [
    ['XX','6D','7D','8D','9D','10D','QD','KD','AD','XX'],
    ['5D','3H','2H','2S','3S','4S','5S','6S','7S','AC'],
    ['4D','4H','KD','AD','AC','KC','QC','10C','8S','KC'],
    ['3D','5H','QD','QH','10H','9H','8H','9C','9S','QC'],
    ['2D','6H','10D','KH','3H','2H','7H','8C','10S','10C'],
    ['AS','7H','9D','AH','4H','5H','6H','7C','QS','9C'],
    ['KS','8H','8D','2C','3C','4C','5C','6C','KS','8C'],
    ['QS','9H','7D','6D','5D','4D','3D','2D','AS','7C'],
    ['10S','10H','QH','KH','AH','2C','3C','4C','5C','6C'],
    ['XX','9S','8S','7S','6S','5S','4S','3S','2S','XX'],
  ];

  const SUIT_SYMBOLS = { S: '\u2660', H: '\u2665', D: '\u2666', C: '\u2663' };
  const SUIT_NAMES = { S: 'spades', H: 'hearts', D: 'diams', C: 'clubs' };
  const RANK_DISPLAY = { '2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9','10':'10','J':'J','Q':'Q','K':'K','A':'A' };

  function parseCard(card) {
    const match = card.match(/^(10|[2-9JQKA])([SHDC])$/);
    if (!match) return null;
    return { rank: match[1], suit: match[2], display: RANK_DISPLAY[match[1]], symbol: SUIT_SYMBOLS[match[2]], cssClass: SUIT_NAMES[match[2]] };
  }

  function isWildJack(card) {
    return card === 'JH' || card === 'JD';
  }

  function isOneEyedJack(card) {
    return card === 'JS' || card === 'JC';
  }

  function isJack(card) {
    return card.endsWith('J') || card === 'JH' || card === 'JD' || card === 'JS' || card === 'JC';
  }

  function cardDisplay(card) {
    if (card === 'JH') return 'JH\u2665';
    if (card === 'JD') return 'JD\u2666';
    if (card === 'JS') return 'JS\u2660';
    if (card === 'JC') return 'JC\u2663';
    const p = parseCard(card);
    return p ? `${p.display}${p.symbol}` : card;
  }

  const state = {
    connected: false,
    ws: null,
    gameId: null,
    players: [],
    board: {},
    hands: {},
    sequences: {},
    currentTurn: 0,
    currentPlayer: null,
    winner: null,
    events: [],
    lastMove: null,
    lastPlayedCard: null,
    seqPositions: new Set(),
    replaying: false,
    replayIndex: 0,
    replaySpeed: 800,
    replayTimer: null,
    gameActive: false,
    playerStats: {},
  };

  const els = {};

  function initElements() {
const ids = [
      'board', 'col-labels', 'row-labels',
      'p1-color', 'p2-color', 'p1-name', 'p2-name', 'p1-model', 'p2-model',
      'p1-sequences', 'p2-sequences', 'p1-hand', 'p2-hand',
      'p1-moves', 'p2-moves', 'p1-avg-time', 'p2-avg-time',
      'p1-tokens', 'p2-tokens', 'p1-avg-tokens', 'p2-avg-tokens',
      'panel-p1', 'panel-p2',
      'turn-indicator', 'turn-player', 'turn-text',
      'log-entries', 'log-status',
'btn-new-game', 'btn-past-games', 'btn-stop-game',
       'modal-overlay', 'modal-close', 'modal-cancel', 'modal-start',
      'modal-past-close', 'modal-past-cancel',
      'p1-provider', 'p1-model-input', 'p2-provider', 'p2-model-input',
      'delay-ms', 'ollama-host',
      'past-games-list',
    ];
    for (const id of ids) {
      els[id.replace(/-/g, '_')] = document.getElementById(id);
    }
  }

  function buildBoard() {
    const board = els.board;
    board.innerHTML = '';

    for (let r = 0; r < 10; r++) {
      for (let c = 0; c < 10; c++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        cell.dataset.row = r;
        cell.dataset.col = c;
        cell.id = `cell-${r}-${c}`;

        const label = BOARD_LAYOUT[r][c];
        const isCorner = label === 'XX';

        if (isCorner) {
          cell.classList.add('corner');
        }

        const labelEl = document.createElement('span');
        labelEl.className = 'cell-label';
        labelEl.textContent = isCorner ? 'XX' : label.replace(/([SHDC])/, '');
        cell.appendChild(labelEl);

        if (!isCorner) {
          const p = parseCard(label);
          if (p) {
            cell.classList.add(`suit-${p.suit.toLowerCase()}`);
            const suitEl = document.createElement('span');
            suitEl.className = 'cell-suit';
            suitEl.textContent = p.symbol;
            cell.appendChild(suitEl);
          }
        }

        board.appendChild(cell);
      }
    }

    const colLabels = els.col_labels;
    colLabels.innerHTML = '';
    for (let c = 0; c < 10; c++) {
      const span = document.createElement('span');
      span.textContent = c;
      colLabels.appendChild(span);
    }

    const rowLabels = els.row_labels;
    rowLabels.innerHTML = '';
    for (let r = 0; r < 10; r++) {
      const span = document.createElement('span');
      span.textContent = r;
      rowLabels.appendChild(span);
    }
  }

function updateBoard() {
    for (let r = 0; r < 10; r++) {
      for (let c = 0; c < 10; c++) {
        const cell = document.getElementById(`cell-${r}-${c}`);
        if (!cell) continue;
        const key = `${r},${c}`;
        const chipValue = state.board[key] || null;
        const existingChip = cell.querySelector('.chip');

        if (chipValue) {
          if (!existingChip || existingChip.dataset.color !== chipValue) {
            if (existingChip) existingChip.remove();
            const chip = document.createElement('div');
            const shortName = state.players.find(p => p.chip === chipValue)?.id?.charAt(0).toUpperCase() || chipValue.charAt(0);
            chip.className = `chip chip-${chipValue}`;
            chip.dataset.color = chipValue;
            chip.textContent = shortName;
            cell.appendChild(chip);
          }
        } else {
          if (existingChip) existingChip.remove();
        }

        const seqKey = `${r},${c}`;
        if (state.seqPositions.has(seqKey)) {
          cell.classList.add('sequence-complete');
        } else {
          cell.classList.remove('sequence-complete');
        }

        const isLastMove = state.lastMove && state.lastMove.position &&
          state.lastMove.position[0] === r && state.lastMove.position[1] === c;
        cell.classList.toggle('last-move', isLastMove);
      }
    }
  }

  function formatKpi(event) {
    const parts = [];
    if (event.move_duration_seconds != null) {
      parts.push(event.move_duration_seconds.toFixed(1) + 's');
    }
    if (event.prompt_tokens != null && event.completion_tokens != null) {
      parts.push((event.prompt_tokens + event.completion_tokens) + 'tok');
    }
    return parts.length > 0 ? parts.join(', ') : '';
  }

  function updateStats() {
    for (const pid of Object.keys(state.playerStats)) {
      const s = state.playerStats[pid];
      const prefix = pid === state.players[0]?.id ? 'p1' : 'p2';
      const movesEl = els[`${prefix}_moves`];
      const avgTimeEl = els[`${prefix}_avg_time`];
      const tokensEl = els[`${prefix}_tokens`];
      const avgTokEl = els[`${prefix}_avg_tokens`];
      if (movesEl) movesEl.textContent = s.total_moves;
      if (avgTimeEl) avgTimeEl.textContent = s.total_moves > 0 ? s.avg_move_duration_seconds.toFixed(1) + 's' : '--';
      if (tokensEl) tokensEl.textContent = s.total_tokens;
      if (avgTokEl) avgTokEl.textContent = s.total_moves > 0 ? s.avg_tokens_per_move.toFixed(0) : '--';
    }
  }

  function updatePanels() {
    for (let i = 0; i < 2; i++) {
      const pIdx = i;
      const prefix = i === 0 ? 'p1' : 'p2';
      const player = state.players[i];
      if (!player) continue;

      const colorEl = els[`${prefix}_color`];
      colorEl.style.backgroundColor = player.chip === 'blue' ? 'var(--chip-blue)' : 'var(--chip-green)';

      els[`${prefix}_name`].textContent = player.id;
      els[`${prefix}_model`].textContent = `${player.provider}/${player.model}`;

      const seqEl = els[`${prefix}_sequences`];
      const newCount = state.sequences[player.id] || 0;
      if (parseInt(seqEl.textContent) !== newCount) {
        seqEl.textContent = newCount;
      }

      const panel = els[`panel_${prefix}`];
      panel.classList.toggle('active', state.currentPlayer === player.id);

      renderHand(prefix, player.id);
    }
  }

  function renderHand(prefix, playerId) {
    const container = els[`${prefix}_hand`];
    const hand = state.hands[playerId] || [];

    if (hand.length === 0 && !state.gameActive) {
      container.innerHTML = '<div class="hand-placeholder">Waiting for game...</div>';
      return;
    }

    const existingCards = container.querySelectorAll('.hand-card');
    const existingSet = new Set();
    existingCards.forEach(el => existingSet.add(el.dataset.card));

    const newSet = new Set(hand);

    container.innerHTML = '';
    for (const card of hand) {
      const cardEl = createHandCard(card);
      container.appendChild(cardEl);
    }
  }

  function createHandCard(card) {
    const el = document.createElement('div');
    el.className = 'hand-card';
    el.dataset.card = card;

    if (isWildJack(card)) {
      el.classList.add('wild-jack');
      const rankEl = document.createElement('span');
      rankEl.className = 'card-rank';
      rankEl.textContent = card === 'JH' ? 'JH' : 'JD';
      el.appendChild(rankEl);
      const suitEl = document.createElement('span');
      suitEl.className = 'card-suit-sm';
      suitEl.textContent = card === 'JH' ? '\u2665' : '\u2666';
      el.appendChild(suitEl);
    } else if (isOneEyedJack(card)) {
      el.style.background = 'linear-gradient(135deg, #c0392b, #96281b)';
      el.style.color = '#fff';
      el.style.borderColor = '#e74c3c';
      const rankEl = document.createElement('span');
      rankEl.className = 'card-rank';
      rankEl.textContent = card === 'JS' ? 'JS' : 'JC';
      el.appendChild(rankEl);
      const suitEl = document.createElement('span');
      suitEl.className = 'card-suit-sm';
      suitEl.textContent = card === 'JS' ? '\u2660' : '\u2663';
      el.appendChild(suitEl);
    } else {
      const p = parseCard(card);
      if (p) {
        el.classList.add(`suit-${p.suit.toLowerCase()}`);
        const rankEl = document.createElement('span');
        rankEl.className = 'card-rank';
        rankEl.textContent = p.display;
        el.appendChild(rankEl);
        const suitEl = document.createElement('span');
        suitEl.className = 'card-suit-sm';
        suitEl.textContent = p.symbol;
        el.appendChild(suitEl);
      }
    }

    return el;
  }

  function updateTurnIndicator() {
    els.turn_indicator.classList.remove('hidden');
    if (state.currentPlayer && state.players.length) {
      const player = state.players.find(p => p.id === state.currentPlayer);
      if (player) {
        els.turn_player.style.backgroundColor = player.chip === 'blue' ? 'var(--chip-blue)' : 'var(--chip-green)';
      }
    }
    els.turn_text.textContent = `Turn ${state.currentTurn}`;
  }

  function addLogEntry(text, cssClass = '') {
    const container = els.log_entries;
    const entry = document.createElement('div');
    entry.className = `log-entry ${cssClass}`;
    entry.innerHTML = text;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;

    const toggle = entry.querySelector('.reason-toggle');
    if (toggle) {
      toggle.addEventListener('click', () => {
        const targetId = toggle.dataset.target;
        const content = document.getElementById(targetId);
        if (content) {
          content.classList.toggle('hidden');
          toggle.innerHTML = content.classList.contains('hidden') ? '&#9654;' : '&#9660;';
        }
      });
    }
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatMove(move) {
    if (!move) return 'unknown';
    const pos = move.position;
    const posStr = pos ? `(${pos[0]},${pos[1]})` : '';

    switch (move.type) {
      case 'place':
        return `placed ${cardDisplay(move.card)} at ${posStr}`;
      case 'two_eyed_jack':
        return `played wild ${cardDisplay(move.card)} at ${posStr}`;
      case 'one_eyed_jack':
        return `removed chip at ${posStr} with ${cardDisplay(move.card)}`;
      case 'dead_card':
        return `discarded dead card ${cardDisplay(move.card)}`;
      default:
        return `${move.type} ${move.card || ''} ${posStr}`;
    }
  }

  function processEvent(event) {
    state.events.push(event);

    try {
    switch (event.type) {
      case 'deal': {
        state.gameActive = true;
        if (event.hand_after) {
          for (const [pid, cards] of Object.entries(event.hand_after)) {
            state.hands[pid] = cards;
          }
        }
        if (event.snapshot) {
          applySnapshot(event.snapshot);
        }
        addLogEntry(`<span class="log-turn">T0</span> Cards dealt. Game started.`);
        updateBoard();
        updatePanels();
        updateTurnIndicator();
        break;
      }
      case 'move': {
        state.lastMove = event.move;
        state.lastMovePlayer = event.player;
        state.lastPlayedCard = event.move ? event.move.card : null;

        if (event.move_duration_seconds != null || event.prompt_tokens != null) {
          if (!state.playerStats[event.player]) {
            state.playerStats[event.player] = { total_moves: 0, total_duration_seconds: 0, total_prompt_tokens: 0, total_completion_tokens: 0, total_tokens: 0, avg_move_duration_seconds: 0, avg_tokens_per_move: 0 };
          }
          const ps = state.playerStats[event.player];
          ps.total_moves += 1;
          ps.total_duration_seconds += event.move_duration_seconds || 0;
          ps.total_prompt_tokens += event.prompt_tokens || 0;
          ps.total_completion_tokens += event.completion_tokens || 0;
          ps.total_tokens = ps.total_prompt_tokens + ps.total_completion_tokens;
          ps.avg_move_duration_seconds = ps.total_moves > 0 ? ps.total_duration_seconds / ps.total_moves : 0;
          ps.avg_tokens_per_move = ps.total_moves > 0 ? ps.total_tokens / ps.total_moves : 0;
        }

        if (event.snapshot) {
          applySnapshot(event.snapshot);
        }

        const playerClass = getPlayerClass(event.player);
        const moveText = `<span class="log-turn">T${event.turn}</span> <span class="log-player ${playerClass}">${event.player}</span> <span class="log-action">${formatMove(event.move)}</span>`;

        const kpiText = formatKpi(event);

        if (event.llm_response) {
          const entryId = `reason-T${event.turn}-${event.player}`;
          addLogEntry(`${moveText}${kpiText ? '<span class="log-kpi">' + kpiText + '</span>' : ''} <button class="reason-toggle" data-target="${entryId}">&#9654;</button><div id="${entryId}" class="reason-content hidden">${escapeHtml(event.llm_response)}</div>`, '');
        } else {
          addLogEntry(`${moveText}${kpiText ? '<span class="log-kpi">' + kpiText + '</span>' : ''}`, '');
        }

        updateBoard();
        updatePanels();
        updateStats();
        updateTurnIndicator();
        break;
      }
      case 'move_after': {
        if (event.snapshot) {
          applySnapshot(event.snapshot);
        }
        state.lastPlayedCard = null;

        updateBoard();
        updatePanels();
        updateTurnIndicator();
        break;
      }
      case 'game_over': {
        state.gameActive = false;
        state.winner = event.move ? event.move.winner : null;

        if (event.snapshot) {
          applySnapshot(event.snapshot);
        }

        const winner = event.move ? event.move.winner : null;
        const reason = event.move ? event.move.reason : 'draw';
        if (winner) {
          const playerClass = getPlayerClass(winner);
          addLogEntry(
            `<span class="log-game-over">\u2605 <span class="log-player ${playerClass}">${winner}</span> WINS! (${reason})</span>`,
            'log-game-over'
          );
        } else {
          addLogEntry('<span class="log-game-over">DRAW - No winner</span>', 'log-game-over');
        }

        els.log_status.textContent = winner ? `${winner} wins!` : 'Draw';

        updateBoard();
        updatePanels();

        document.querySelectorAll('.player-panel').forEach(p => p.classList.remove('active'));

        break;
      }
      case 'draw': {
        if (event.snapshot) {
          applySnapshot(event.snapshot);
        }
        addLogEntry(`<span class="log-turn">T${event.turn}</span> No legal moves. Game drawn.`, 'log-game-over');
        updateBoard();
        updatePanels();
        break;
      }
    }
    } catch (err) {
      console.error('[Sequence] processEvent error:', err, event);
    }
  }

  function applySnapshot(snapshot) {
    if (snapshot.board) {
      state.board = snapshot.board;
    }
    if (snapshot.hands) {
      for (const [pid, cards] of Object.entries(snapshot.hands)) {
        state.hands[pid] = cards;
      }
    }
    if (snapshot.sequences) {
      state.sequences = snapshot.sequences;
    }
    if (snapshot.current_player) {
      state.currentPlayer = snapshot.current_player;
    }
    if (snapshot.turn_number !== undefined) {
      state.currentTurn = snapshot.turn_number;
    }
    if (snapshot.winner) {
      state.winner = snapshot.winner;
    }
    if (snapshot.players && snapshot.chips) {
      state.players = snapshot.players.map(pid => {
        const existing = state.players.find(p => p.id === pid);
        return {
          id: pid,
          model: existing ? existing.model : '?',
          provider: existing ? existing.provider : '?',
          chip: snapshot.chips[pid] || '?',
        };
      });
    }
  }

  function getPlayerClass(playerId) {
    const player = state.players.find(p => p.id === playerId);
    if (!player) return '';
    return player.chip === 'blue' ? 'p1' : 'p2';
  }

  function resetState() {
    state.board = {};
    state.hands = {};
    state.sequences = {};
    state.currentTurn = 0;
    state.currentPlayer = null;
    state.winner = null;
    state.events = [];
    state.lastMove = null;
    state.lastPlayedCard = null;
    state.lastMovePlayer = null;
    state.seqPositions = new Set();
    state.gameActive = true;
    state.playerStats = {};

    for (const p of state.players) {
      state.hands[p.id] = [];
      state.sequences[p.id] = 0;
    }

    els.log_entries.innerHTML = '';
    els.log_status.textContent = '';

    for (const prefix of ['p1', 'p2']) {
      const movesEl = els[`${prefix}_moves`];
      const avgTimeEl = els[`${prefix}_avg_time`];
      const tokensEl = els[`${prefix}_tokens`];
      const avgTokEl = els[`${prefix}_avg_tokens`];
      if (movesEl) movesEl.textContent = '0';
      if (avgTimeEl) avgTimeEl.textContent = '--';
      if (tokensEl) tokensEl.textContent = '0';
      if (avgTokEl) avgTokEl.textContent = '--';
    }

    document.querySelectorAll('.player-panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.cell').forEach(c => {
      const chip = c.querySelector('.chip');
      if (chip) chip.remove();
      c.classList.remove('sequence-complete', 'last-move', 'sequence-flash');
    });
  }

  // ---------- RESIZE ----------

  function initResize() {
    const handle = document.getElementById('resize-handle');
    const logSection = document.getElementById('log-section');
    if (!handle || !logSection) return;

    let startY = 0;
    let startHeight = 0;

    handle.addEventListener('mousedown', (e) => {
      startY = e.clientY;
      startHeight = logSection.offsetHeight;
      document.addEventListener('mousemove', onMouseMove);
      document.addEventListener('mouseup', onMouseUp);
      e.preventDefault();
    });

    function onMouseMove(e) {
      const delta = startY - e.clientY;
      const newHeight = Math.max(80, Math.min(window.innerHeight * 0.7, startHeight + delta));
      logSection.style.height = newHeight + 'px';
    }

    function onMouseUp() {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    }
  }

  // ---------- WEBSOCKET ----------

  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${location.host}/ws/live`;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
      state.connected = true;
      els.log_status.textContent = 'Connected';
      els.log_status.style.color = 'var(--green)';
    };

    state.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
      } catch (err) {
        console.error('[Sequence] WS message error:', err);
      }
    };

    state.ws.onclose = () => {
      state.connected = false;
      els.log_status.textContent = 'Disconnected';
      els.log_status.style.color = 'var(--red)';
      setTimeout(connectWS, 3000);
    };

    state.ws.onerror = () => {
      state.connected = false;
    };
  }

  function handleWSMessage(msg) {
    switch (msg.type) {
      case 'game_event': {
        processEvent(msg.event);
        break;
      }
      case 'game_saved': {
        addLogEntry(`<span class="log-game-over">Game log saved (ID: ${msg.game_id})</span>`, 'log-game-over');
        break;
      }
      case 'game_cancelled': {
        state.gameActive = false;
        addLogEntry('<span class="log-game-over" style="color:var(--red)">Game stopped</span>', 'log-game-over');
        els.log_status.textContent = 'Game stopped';
        els.log_status.style.color = 'var(--red)';
        break;
      }
      case 'game_error': {
        addLogEntry(`<span class="log-game-over" style="color:var(--red)">Error: ${msg.error}</span>`, 'log-game-over');
        break;
      }
      case 'replay': {
        state.gameId = msg.game_id;
        for (const evt of msg.events) {
          processEvent(evt);
        }
        break;
      }
      case 'ping': {
        state.ws && state.ws.send(JSON.stringify({ type: 'pong' }));
        break;
      }
    }
  }

  // ---------- STOP GAME ----------

  function stopActiveGame() {
    if (state.gameId && state.gameActive) {
      fetch('/api/games/active', { method: 'DELETE' })
        .then(() => {
          state.gameActive = false;
          els.log_status.textContent = 'Game stopped';
          els.log_status.style.color = 'var(--red)';
        })
        .catch(() => {});
    }
  }

  // ---------- NEW GAME ----------

  function startNewGame() {
    stopActiveGame();

    const config = {
      p1_provider: els.p1_provider.value,
      p1_model: els.p1_model_input.value || 'llama3',
      p2_provider: els.p2_provider.value,
      p2_model: els.p2_model_input.value || 'llama3',
      delay_ms: parseInt(els.delay_ms.value) || 800,
      ollama_host: els.ollama_host.value || 'http://localhost:11434',
    };

    state.players = [
      { id: 'player1', model: config.p1_model, provider: config.p1_provider, chip: 'blue' },
      { id: 'player2', model: config.p2_model, provider: config.p2_provider, chip: 'green' },
    ];

    resetState();
    updatePanels();
    updateTurnIndicator();

    els.modal_overlay.classList.add('hidden');
    els.log_status.textContent = 'Starting game...';
    els.log_status.style.color = 'var(--gold)';

    fetch('/api/games', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    })
    .then(r => r.json())
    .then(data => {
      state.gameId = data.game_id;
      els.log_status.textContent = `Game ${data.game_id} started`;
      els.log_status.style.color = 'var(--green)';
    })
    .catch(err => {
      els.log_status.textContent = `Error: ${err.message}`;
      els.log_status.style.color = 'var(--red)';
    });
  }

  // ---------- PAST GAMES ----------

  function loadPastGames() {
    fetch('/api/games')
      .then(r => r.json())
      .then(games => {
        const container = els.past_games_list;
        container.innerHTML = '';
        if (games.length === 0) {
          container.innerHTML = '<div class="log-empty">No past games found.</div>';
          return;
        }
        for (const game of games) {
          const item = document.createElement('div');
          item.className = 'past-game-item';

          const p1 = game.players?.[0];
          const p2 = game.players?.[1];
          const playersStr = p1 && p2
            ? `${p1.id} (${p1.provider}/${p1.model}) vs ${p2.id} (${p2.provider}/${p2.model})`
            : 'Unknown players';

          const statusClass = game.winner ? 'won' : 'draw';
          const statusText = game.winner ? `${game.winner} Won` : 'Draw';

          let statsHtml = '';
          if (game.player_stats) {
            const statsLines = [];
            for (const [pid, ps] of Object.entries(game.player_stats)) {
              statsLines.push(`${pid}: ${ps.avg_move_duration_seconds}s/move, ${ps.total_tokens}tok, ${ps.avg_tokens_per_move}tok/move`);
            }
            if (statsLines.length) {
              statsHtml = `<div class="past-game-stats">${statsLines.join(' | ')}</div>`;
            }
          }

          item.innerHTML = `
            <div class="past-game-info">
              <div class="past-game-players">${playersStr}</div>
              <div class="past-game-meta">${game.created_at ? new Date(game.created_at).toLocaleString() : ''} &middot; ${game.event_count || 0} events</div>
              ${statsHtml}
            </div>
            <div class="past-game-status ${statusClass}">${statusText}</div>
          `;

          item.addEventListener('click', () => loadGame(game.game_id));
          container.appendChild(item);
        }
      })
      .catch(err => {
        els.past_games_list.innerHTML = `<div class="log-empty">Error loading games: ${err.message}</div>`;
      });
  }

  function loadGame(gameId) {
    fetch(`/api/games/${gameId}`)
      .then(r => r.json())
      .then(data => {
        state.gameId = data.game_id;
        state.players = data.players || [];
        resetState();
        updatePanels();

        for (const evt of data.events || []) {
          processEvent(evt);
        }

        els.modal_overlay.classList.add('hidden');
        els.log_status.textContent = `Replaying game ${gameId}`;
        els.log_status.style.color = 'var(--accent)';
      })
      .catch(err => {
        alert(`Error loading game: ${err.message}`);
      });
  }

  // ---------- EVENT HANDLERS ----------

  function bindEvents() {
    els.btn_new_game.addEventListener('click', () => {
      els.modal_overlay.classList.remove('hidden');
      document.getElementById('modal-new-game').classList.remove('hidden');
      document.getElementById('modal-past-games').classList.add('hidden');
    });

    els.btn_past_games.addEventListener('click', () => {
      loadPastGames();
      els.modal_overlay.classList.remove('hidden');
      document.getElementById('modal-new-game').classList.add('hidden');
      document.getElementById('modal-past-games').classList.remove('hidden');
    });

    els.modal_close.addEventListener('click', () => {
      els.modal_overlay.classList.add('hidden');
    });

    els.modal_cancel.addEventListener('click', () => {
      els.modal_overlay.classList.add('hidden');
    });

    els.modal_start.addEventListener('click', startNewGame);

    els.btn_stop_game.addEventListener('click', stopActiveGame);

    els.modal_past_close.addEventListener('click', () => {
      els.modal_overlay.classList.add('hidden');
    });

    els.modal_past_cancel.addEventListener('click', () => {
      els.modal_overlay.classList.add('hidden');
    });

    els.modal_overlay.addEventListener('click', (e) => {
      if (e.target === els.modal_overlay) {
        els.modal_overlay.classList.add('hidden');
      }
    });

    const p1Provider = els.p1_provider;
    const p1ModelInput = els.p1_model_input;
    const p2Provider = els.p2_provider;
    const p2ModelInput = els.p2_model_input;

    const modelDefaults = { ollama: 'llama3', openai: 'gpt-4o', anthropic: 'claude-sonnet-4-20250514' };

    p1Provider.addEventListener('change', () => {
      p1ModelInput.placeholder = modelDefaults[p1Provider.value] || '';
      if (!p1ModelInput.value || Object.values(modelDefaults).includes(p1ModelInput.value)) {
        p1ModelInput.value = modelDefaults[p1Provider.value] || '';
      }
    });

    p2Provider.addEventListener('change', () => {
      p2ModelInput.placeholder = modelDefaults[p2Provider.value] || '';
      if (!p2ModelInput.value || Object.values(modelDefaults).includes(p2ModelInput.value)) {
        p2ModelInput.value = modelDefaults[p2Provider.value] || '';
      }
    });
  }

  // ---------- INIT ----------

  function init() {
    initElements();
    buildBoard();
    bindEvents();
    initResize();
    connectWS();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(window);