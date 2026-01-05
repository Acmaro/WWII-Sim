// Multi-Agent Game JavaScript Logic

const API_BASE = 'http://localhost:8001';

// Global State
let gameState = {
    sessionId: null,
    playerCountry: null,
    worldState: null,
    currentTurn: 1,
    agentOptions: {},  // country -> options[]
    aiChoices: {},     // country -> choice
    playerChoice: null
};

// Country Configuration
const COUNTRY_CONFIG = {
    'GER': { name: 'Germany', flag: '🦅', color: '#e74c3c' },
    'UK': { name: 'United Kingdom', flag: '🦁', color: '#3498db' },
    'USSR': { name: 'Soviet Union', flag: '⭐', color: '#e67e22' }
};

// ============================================================================
// Country Selection
// ============================================================================

function selectCountry(country) {
    // Remove all selected states
    document.querySelectorAll('.country-card').forEach(card => {
        card.classList.remove('selected');
    });

    // Add selected state
    document.querySelector(`[data-country="${country}"]`).classList.add('selected');

    // Set player country
    gameState.playerCountry = country;

    // Enable start button
    document.getElementById('startGameBtn').disabled = false;

    console.log('Selected country:', country);
}

// ============================================================================
// Start Game
// ============================================================================

async function startGame() {
    if (!gameState.playerCountry) {
        alert('Please select a country first');
        return;
    }

    console.log('Starting multi-agent game...', gameState.playerCountry);

    try {
        const response = await fetch(`${API_BASE}/api/multi-agent/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                player_country: gameState.playerCountry
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start');
        }

        const data = await response.json();
        console.log('Game started successfully:', data);

        gameState.sessionId = data.session_id;
        gameState.worldState = data.world_state;

        // Hide selection screen, show game interface
        document.getElementById('countrySelection').classList.add('hidden');
        document.getElementById('gameInterface').classList.remove('hidden');

        // Initialize interface
        initializeGameInterface(data);

        // Start first turn
        setTimeout(() => executeTurn(), 500);

    } catch (error) {
        console.error('Failed to start game:', error);
        alert(`Start failed: ${error.message}`);
    }
}

function initializeGameInterface(data) {
    // Update control badges
    for (const country of ['GER', 'UK', 'USSR']) {
        const badge = document.getElementById(`badge-${country}`);
        const panel = document.getElementById(`panel-${country}`);

        if (country === gameState.playerCountry) {
            badge.textContent = 'Player Control';
            badge.className = 'control-badge player';
            panel.classList.add('player');
        } else {
            badge.textContent = 'AI Control';
            badge.className = 'control-badge ai';
            panel.classList.add('ai');
        }
    }

    // Update resources
    updateResources(data.world_state);
}

// ============================================================================
// 执行回合
// ============================================================================

async function executeTurn() {
    // 显示加载状态
    showLoading();

    try {
        const response = await fetch(`${API_BASE}/api/multi-agent/turn`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: gameState.sessionId
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '执行回合失败');
        }

        const data = await response.json();

        // 更新回合数
        gameState.currentTurn = data.turn_number;
        gameState.agentOptions = data.agent_options;
        gameState.aiChoices = data.ai_choices;

        console.log(`\n执行回合 ${gameState.currentTurn}`);
        console.log('回合数据:', data);

        // 更新界面
        updateTurnInfo();
        displayAllOptions(data);

        hideLoading();

    } catch (error) {
        console.error('执行回合失败:', error);
        alert(`执行回合失败: ${error.message}`);
        hideLoading();
    }
}

function updateTurnInfo() {
    document.getElementById('turnNumber').textContent = `Turn ${gameState.currentTurn}`;
}

// ============================================================================
// 显示选项
// ============================================================================

function displayAllOptions(data) {
    for (const country of ['GER', 'UK', 'USSR']) {
        const container = document.getElementById(`options-${country}`);
        const options = data.agent_options[country] || [];

        if (country === gameState.playerCountry) {
            // 玩家国家：显示可选择的选项
            displayPlayerOptions(container, options, country);
        } else {
            // AI国家：显示AI的选择
            const aiChoice = data.ai_choices[country];
            displayAIChoice(container, aiChoice, country);
        }
    }
}

function displayPlayerOptions(container, options, country) {
    if (options.length === 0) {
        container.innerHTML = '<div class="loading">生成选项中...</div>';
        return;
    }

    let html = '<h3 style="margin-bottom: 15px;">选择你的行动：</h3>';

    options.forEach(option => {
        html += `
            <div class="option-card" data-option-id="${option.id}" onclick="selectOption('${option.id}')">
                <div class="option-header">
                    <span class="option-name">${option.name}</span>
                    <span class="option-type type-${option.event_type}">${getTypeIcon(option.event_type)}</span>
                </div>
                <div class="option-description">${option.description}</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function displayAIChoice(container, choice, country) {
    if (!choice) {
        container.innerHTML = '<div class="loading"><div class="spinner"></div>AI决策中...</div>';
        return;
    }

    const html = `
        <div class="ai-choice">
            <div class="ai-choice-label">AI选择:</div>
            <div class="ai-choice-content">
                ${getTypeIcon(choice.event_type)} ${choice.name}
            </div>
            <div style="margin-top: 8px; font-size: 0.9em; opacity: 0.8;">
                ${choice.description}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function getTypeIcon(type) {
    const icons = {
        'military': '⚔️ Military',
        'diplomatic': '🤝 Diplomatic',
        'economic': '💰 Economic',
        'political': '📢 Political'
    };
    return icons[type] || type;
}

// ============================================================================
// 选择选项
// ============================================================================

function selectOption(optionId) {
    // 移除所有选中状态
    document.querySelectorAll('.option-card').forEach(card => {
        card.classList.remove('selected');
    });

    // 添加选中状态
    document.querySelector(`[data-option-id="${optionId}"]`).classList.add('selected');

    // 记录选择
    gameState.playerChoice = optionId;

    // 启用确认按钮
    document.getElementById('confirmBtn').disabled = false;

    console.log('选择行动:', optionId);
}

// ============================================================================
// 确认选择
// ============================================================================

async function confirmChoice() {
    if (!gameState.playerChoice) {
        alert('请先选择一个行动');
        return;
    }

    console.log('提交选择:', gameState.playerChoice);

    // 禁用确认按钮
    document.getElementById('confirmBtn').disabled = true;

    // 显示加载
    showLoading('处理所有国家的行动...');

    try {
        const response = await fetch(`${API_BASE}/api/multi-agent/player-choice`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: gameState.sessionId,
                choice_id: gameState.playerChoice
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '提交失败');
        }

        const data = await response.json();
        console.log('回合结果:', data);

        hideLoading();

        // 显示回合结果
        displayTurnResult(data.turn_result);

        // 获取并更新世界状态（更新资源显示）
        await updateWorldState();

        // 清空选择
        gameState.playerChoice = null;

        // 检查游戏是否结束
        if (data.turn_result.is_game_over) {
            console.log('[游戏结束]', data.turn_result.ending_trigger);

            // 显示结局提示，询问是否生成完整结局
            setTimeout(() => {
                if (confirm(`游戏结束！\n原因：${data.turn_result.ending_trigger}\n\n是否让AI生成完整的结局故事？`)) {
                    generateEnding();
                }
            }, 2000);
        } else {
            // 延迟后开始下一回合（不隐藏结果）
            setTimeout(() => {
                executeTurn();
            }, 3000);
        }

    } catch (error) {
        console.error('提交选择失败:', error);
        alert(`提交失败: ${error.message}`);
        document.getElementById('confirmBtn').disabled = false;
        hideLoading();
    }
}

// ============================================================================
// 显示回合结果
// ============================================================================

function displayTurnResult(result) {
    const panel = document.getElementById('turnResult');
    const turnId = `turn-${result.turn_number}`;

    // 构建回合内容
    let contentHtml = '';

    // 所有国家的行动
    contentHtml += '<div class="result-section">';
    contentHtml += '<h3>各国行动</h3>';
    for (const [country, action] of Object.entries(result.all_actions)) {
        const config = COUNTRY_CONFIG[country];
        contentHtml += `
            <div class="event-item">
                <strong>${config.flag} ${config.name}</strong>: ${action.name}
                <span class="option-type type-${action.type}" style="margin-left: 10px;">
                    ${getTypeIcon(action.type)}
                </span>
                <div style="margin-top: 5px; opacity: 0.8; font-size: 0.9em;">
                    ${action.description}
                </div>
            </div>
        `;
    }
    contentHtml += '</div>';

    // 外交影响（去重合并）
    if (result.diplomatic_changes && result.diplomatic_changes.length > 0) {
        contentHtml += '<div class="result-section">';
        contentHtml += '<h3>外交关系变化</h3>';

        // 合并重复的关系对
        const relationMap = new Map();
        result.diplomatic_changes.forEach(change => {
            // 创建统一的key（总是字母序小的在前）
            const key = [change.country1, change.country2].sort().join('-');

            if (!relationMap.has(key)) {
                relationMap.set(key, {
                    countries: [change.country1, change.country2].sort(),
                    initial_value: change.old_value,
                    final_value: change.new_value,
                    reasons: [change.reason]
                });
            } else {
                // 更新最终值和原因
                const existing = relationMap.get(key);
                existing.final_value = change.new_value;
                existing.reasons.push(change.reason);
            }
        });

        // 显示合并后的关系变化
        relationMap.forEach((data, key) => {
            const [c1, c2] = data.countries;
            const totalDelta = data.final_value - data.initial_value;
            const arrow = totalDelta > 0 ? '↑' : '↓';
            const color = totalDelta > 0 ? '#28a745' : '#dc3545';

            contentHtml += `
                <div class="event-item">
                    ${c1} ↔ ${c2}:
                    ${data.initial_value.toFixed(2)} → ${data.final_value.toFixed(2)}
                    <span style="color: ${color}; margin-left: 10px;">${arrow} ${Math.abs(totalDelta).toFixed(2)}</span>
                    <div style="opacity: 0.8; font-size: 0.9em;">
                        ${data.reasons.join('、')}
                    </div>
                </div>
            `;
        });
        contentHtml += '</div>';
    }

    // 经济变化
    if (result.economic_changes && result.economic_changes.length > 0) {
        contentHtml += '<div class="result-section">';
        contentHtml += '<h3>资源变化</h3>';
        result.economic_changes.forEach(change => {
            const arrow = change.delta > 0 ? '↑' : '↓';
            const color = change.delta > 0 ? '#28a745' : '#dc3545';
            contentHtml += `
                <div class="event-item">
                    ${change.country} - ${change.resource}:
                    ${change.old_value} → ${change.new_value}
                    <span style="color: ${color}; margin-left: 10px;">${arrow} ${Math.abs(change.delta)}</span>
                    <div style="opacity: 0.8; font-size: 0.9em;">${change.reason}</div>
                </div>
            `;
        });
        contentHtml += '</div>';
    }

    // 创建可折叠的回合结果div
    const turnDiv = document.createElement('div');
    turnDiv.className = 'turn-result-item';
    turnDiv.id = turnId;
    turnDiv.style.marginBottom = '15px';
    turnDiv.style.borderRadius = '10px';
    turnDiv.style.overflow = 'hidden';
    turnDiv.style.background = 'rgba(255, 255, 255, 0.1)';
    turnDiv.style.border = '2px solid rgba(255, 215, 0, 0.3)';

    // 标题栏（可点击折叠）
    const headerDiv = document.createElement('div');
    headerDiv.style.padding = '12px 15px';
    headerDiv.style.background = 'rgba(255, 215, 0, 0.2)';
    headerDiv.style.cursor = 'pointer';
    headerDiv.style.display = 'flex';
    headerDiv.style.justifyContent = 'space-between';
    headerDiv.style.alignItems = 'center';
    headerDiv.style.userSelect = 'none';
    headerDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.2em; color: #ffd700;">📜</span>
            <strong style="font-size: 1.1em; color: #ffd700;">回合 ${result.turn_number} 结果</strong>
        </div>
        <span class="collapse-icon" style="font-size: 1.2em; transition: transform 0.3s;">▼</span>
    `;

    // 内容区域
    const contentDiv = document.createElement('div');
    contentDiv.className = 'turn-content';
    contentDiv.style.padding = '15px';
    contentDiv.style.maxHeight = '1000px';
    contentDiv.style.overflow = 'hidden';
    contentDiv.style.transition = 'max-height 0.3s ease-out';
    contentDiv.innerHTML = contentHtml;

    // 折叠/展开功能
    let isExpanded = true;
    headerDiv.onclick = () => {
        isExpanded = !isExpanded;
        const icon = headerDiv.querySelector('.collapse-icon');

        if (isExpanded) {
            contentDiv.style.maxHeight = '1000px';
            icon.style.transform = 'rotate(0deg)';
        } else {
            contentDiv.style.maxHeight = '0';
            icon.style.transform = 'rotate(-90deg)';
        }
    };

    turnDiv.appendChild(headerDiv);
    turnDiv.appendChild(contentDiv);

    // 折叠所有旧的回合
    const existingTurns = panel.querySelectorAll('.turn-result-item');
    existingTurns.forEach(oldTurn => {
        const oldContent = oldTurn.querySelector('.turn-content');
        const oldIcon = oldTurn.querySelector('.collapse-icon');
        if (oldContent && oldIcon) {
            oldContent.style.maxHeight = '0';
            oldIcon.style.transform = 'rotate(-90deg)';
        }
    });

    // 追加到顶部（最新的在上面）
    panel.insertBefore(turnDiv, panel.firstChild);
    panel.classList.remove('hidden');

    // 滚动到最新结果
    setTimeout(() => {
        turnDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

// ============================================================================
// 更新资源
// ============================================================================

async function updateWorldState() {
    try {
        const response = await fetch(`${API_BASE}/api/multi-agent/world?session_id=${gameState.sessionId}`);

        if (!response.ok) {
            console.error('获取世界状态失败');
            return;
        }

        const worldState = await response.json();
        gameState.worldState = worldState;

        // 更新资源显示
        updateResources(worldState);

        console.log('世界状态已更新');
    } catch (error) {
        console.error('更新世界状态失败:', error);
    }
}

function updateResources(worldState) {
    for (const [country, agent] of Object.entries(worldState.agents)) {
        const resources = agent.resources || {};

        document.getElementById(`military-${country}`).textContent =
            Math.round(resources.military || 100);
        document.getElementById(`economic-${country}`).textContent =
            Math.round(resources.economic || 100);
        document.getElementById(`diplomatic-${country}`).textContent =
            Math.round(resources.diplomatic || 100);
    }
}

// ============================================================================
// 加载状态
// ============================================================================

function showLoading(message = '加载中...') {
    // 在每个选项容器中显示加载
    for (const country of ['GER', 'UK', 'USSR']) {
        const container = document.getElementById(`options-${country}`);
        container.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                ${message}
            </div>
        `;
    }
}

function hideLoading() {
    // 由displayAllOptions处理
}

// ============================================================================
// 结局生成
// ============================================================================

async function generateEnding() {
    console.log('开始生成结局...');

    // 显示加载界面
    showLoading('AI正在生成结局故事，请稍候...');

    // 隐藏确认按钮（游戏已结束）
    document.getElementById('confirmBtn').style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/api/multi-agent/simulate-ending`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: gameState.sessionId
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '生成结局失败');
        }

        const ending = await response.json();
        console.log('结局生成成功:', ending);

        hideLoading();

        // 显示结局界面
        displayEnding(ending);

    } catch (error) {
        console.error('生成结局失败:', error);
        alert(`生成结局失败: ${error.message}`);
        hideLoading();
    }
}

function displayEnding(ending) {
    // 隐藏游戏界面
    document.getElementById('gameInterface').style.display = 'none';

    // 创建结局界面
    const endingContainer = document.createElement('div');
    endingContainer.id = 'endingScreen';
    endingContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, #1a1a2e 0%, #0f0f1e 100%);
        overflow-y: auto;
        z-index: 9999;
        padding: 40px 20px;
    `;

    // 确定结局标题和颜色
    let titleText = '游戏结束';
    let titleColor = '#ffd700';

    if (ending.ending_type === 'victory') {
        titleText = '🎉 胜利！';
        titleColor = '#00ff00';
    } else if (ending.ending_type === 'defeat') {
        titleText = '💔 失败';
        titleColor = '#ff4444';
    } else if (ending.ending_type === 'historical') {
        titleText = '📜 历史结局';
        titleColor = '#ffd700';
    }

    endingContainer.innerHTML = `
        <div style="max-width: 1000px; margin: 0 auto;">
            <!-- 标题 -->
            <h1 style="text-align: center; color: ${titleColor}; font-size: 3em; margin-bottom: 20px; text-shadow: 0 0 20px ${titleColor};">
                ${titleText}
            </h1>

            <div style="text-align: center; color: #aaa; margin-bottom: 40px; font-size: 1.2em;">
                ${ending.trigger_reason}
            </div>

            <!-- 结局叙事 -->
            <div style="background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 15px; margin-bottom: 30px; border: 2px solid rgba(255, 215, 0, 0.3);">
                <h2 style="color: #ffd700; margin-bottom: 20px; text-align: center;">📖 历史叙事</h2>
                <div style="color: #eee; line-height: 1.8; font-size: 1.1em; text-align: justify; white-space: pre-wrap;">
${ending.narrative}
                </div>
            </div>

            <!-- 各国后续发展 -->
            <div style="background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 15px; margin-bottom: 30px; border: 2px solid rgba(255, 215, 0, 0.3);">
                <h2 style="color: #ffd700; margin-bottom: 20px; text-align: center;">🌍 各国后续发展</h2>
                <div style="display: grid; gap: 15px;">
                    ${Object.entries(ending.epilogue).map(([country, text]) => {
                        const config = COUNTRY_CONFIG[country];
                        return `
                            <div style="padding: 15px; background: rgba(255, 255, 255, 0.05); border-radius: 10px;">
                                <div style="color: ${config.color}; font-weight: bold; margin-bottom: 8px; font-size: 1.1em;">
                                    ${config.flag} ${config.name}
                                </div>
                                <div style="color: #ccc; line-height: 1.6;">
                                    ${text}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>

            <!-- 最终统计 -->
            <div style="background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 15px; margin-bottom: 30px; border: 2px solid rgba(255, 215, 0, 0.3);">
                <h2 style="color: #ffd700; margin-bottom: 20px; text-align: center;">📊 最终统计</h2>
                <div style="text-align: center; margin-bottom: 20px; color: #aaa; font-size: 1.1em;">
                    游戏时长：${ending.final_stats.total_turns} 回合 | 结束时间：${ending.final_stats.end_date}
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px;">
                    ${Object.entries(ending.final_stats.countries).map(([code, data]) => {
                        const config = COUNTRY_CONFIG[code];
                        return `
                            <div style="padding: 20px; background: rgba(255, 255, 255, 0.05); border-radius: 10px; border: 2px solid ${config.color};">
                                <div style="text-align: center; color: ${config.color}; font-weight: bold; font-size: 1.2em; margin-bottom: 15px;">
                                    ${config.flag} ${data.name}
                                </div>
                                <div style="color: #ccc;">
                                    <div style="margin-bottom: 8px;">⚔️ Military: ${data.resources.military}</div>
                                    <div style="margin-bottom: 8px;">💰 Economic: ${data.resources.economic}</div>
                                    <div style="margin-bottom: 8px;">🤝 Diplomatic: ${data.resources.diplomatic}</div>
                                    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1);">
                                        总行动数: ${data.total_actions}
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>

            <!-- 关键事件回顾 -->
            ${ending.key_events && ending.key_events.length > 0 ? `
                <div style="background: rgba(255, 255, 255, 0.05); padding: 30px; border-radius: 15px; margin-bottom: 30px; border: 2px solid rgba(255, 215, 0, 0.3);">
                    <h2 style="color: #ffd700; margin-bottom: 20px; text-align: center;">⭐ 关键历史事件</h2>
                    <div style="color: #ccc; line-height: 1.8;">
                        ${ending.key_events.map(event => `<div style="margin-bottom: 10px;">• ${event}</div>`).join('')}
                    </div>
                </div>
            ` : ''}

            <!-- 重新开始按钮 -->
            <div style="text-align: center; margin-top: 40px;">
                <button onclick="location.reload()" style="
                    padding: 15px 40px;
                    font-size: 1.2em;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                    transition: all 0.3s;
                ">
                    🔄 重新开始游戏
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(endingContainer);

    // 滚动到顶部
    window.scrollTo(0, 0);
}

// ============================================================================
// 初始化
// ============================================================================

console.log('多Agent游戏前端已加载');
console.log('API地址:', API_BASE);
