# WWIISim-v2 Prompt模板汇总文档

> **版本**: 2.0
> **最后更新**: 2026-01-02
> **作者**: Claude AI

---

## 目录

1. [事件生成类Prompt](#事件生成类prompt)
2. [AI决策类Prompt](#ai决策类prompt)
3. [结局生成类Prompt](#结局生成类prompt)
4. [Prompt设计原则](#prompt设计原则)
5. [使用场景总结](#使用场景总结)

---

## 事件生成类Prompt

### 1. 基础事件草稿生成 (Event Generation Workflow)

**文件位置**: `backend/workflows/event_generation.py:146-184`

**使用场景**:
- 单Agent模式的事件生成
- 不考虑Agent性格特征
- 基于历史RAG和当前态势

**触发时机**: 每回合开始，为玩家生成4个选项

**Prompt模板**:
```python
"""你是一位精通二战历史的专家和游戏设计师。

【历史背景参考】
{rag_context}

【当前游戏态势】
国家: {country}
时间: {year}年{month}月
历史: {history_summary}

【任务】
为{country}生成4个不同的战略选项。

【要求】
1. 4个选项类型必须完全不同:
   - military (军事)
   - diplomatic (外交)
   - economic (经济)
   - political (政治)

2. 每个选项必须:
   - 符合历史背景和当前态势
   - 具有明确的行动和预期结果
   - likelihood评分合理（0.0-1.0）
   - 描述简洁（20-80字，越短越好）

3. 选项应该涵盖不同的战略方向:
   - 激进进攻型
   - 稳健扩张型
   - 防御巩固型
   - 外交政治型

4. reasoning字段说明为什么这些选项合理且多样

{format_instructions}

直接输出JSON，不要添加markdown代码块标记或解释文字。
"""
```

**输入参数**:
- `rag_context`: RAG检索到的历史事件上下文（5条）
- `country`: 国家代码（GER/UK/USSR）
- `year`: 当前年份（1939-1945）
- `month`: 当前月份（1-12）
- `history_summary`: 玩家历史行动摘要
- `format_instructions`: Pydantic输出格式说明

**输出格式**: `BranchOptions` (Pydantic模型)
```json
{
  "branches": [
    {
      "id": "military_001",
      "name": "闪电战波兰",
      "description": "发动快速机械化进攻，迅速占领波兰",
      "event_type": "military",
      "year": 1939,
      "month": 9,
      "likelihood": 0.85
    },
    // ...3 more events
  ],
  "reasoning": "这些选项覆盖了军事、外交、经济、政治四个维度..."
}
```

---

### 2. 多Agent事件草稿生成 (Multi-Agent Generation)

**文件位置**: `backend/workflows/multi_agent_generation.py:236-274`

**使用场景**:
- 多Agent模式（3国同时运行）
- **考虑Agent性格特征**（激进度、外交倾向、经济重视、风险承受度）
- 考虑世界状态和其他国家行动

**触发时机**: 每回合开始，并行为3个国家生成选项

**Prompt模板**:
```python
"""
你是{country_name}的战略顾问AI。

【Agent性格特征】
激进度: {aggression} (0-1, 越高越倾向军事行动)
外交倾向: {diplomacy} (0-1, 越高越倾向外交手段)
经济重视度: {economic_focus} (0-1, 越高越重视经济发展)
风险承受度: {risk_tolerance} (0-1, 越高越敢冒险)

【战略目标】
{objectives}

【历史背景与当前态势】
{rag_context}

【任务】
根据Agent的性格特征和战略目标，生成4个符合角色定位的行动选项。

【要求】
1. **选项类型分布应符合Agent性格**:
   - 如果 aggression >= 0.7: 至少2个 military 选项
   - 如果 diplomacy >= 0.7: 至少2个 diplomatic 选项
   - 如果 economic_focus >= 0.7: 至少2个 economic 选项
   - 否则: 4种类型各1个（military, diplomatic, economic, political）

2. **风险程度匹配 risk_tolerance**:
   - 高风险承受(>0.6): 可以有大胆冒险的选项
   - 低风险承受(<0.4): 选项应该稳健保守

3. 每个选项必须:
   - 符合历史背景和当前态势
   - 考虑与其他国家的关系
   - 描述简洁（20-80字）
   - likelihood 评分合理（0.0-1.0）

{format_instructions}

直接输出JSON，不要添加markdown代码块标记或解释文字。
"""
```

**输入参数**:
- `country_name`: 国家名称（德国/英国/苏联）
- `aggression`: Agent激进度（0.0-1.0）
- `diplomacy`: Agent外交倾向（0.0-1.0）
- `economic_focus`: Agent经济重视度（0.0-1.0）
- `risk_tolerance`: Agent风险承受度（0.0-1.0）
- `objectives`: Agent战略目标列表（3-5条）
- `rag_context`: 增强的上下文（包含RAG历史、世界态势、其他国家行动）
- `format_instructions`: Pydantic格式说明

**关键差异**:
- ✅ 性格特征驱动生成
- ✅ 动态调整选项类型分布
- ✅ 风险程度匹配Agent性格
- ✅ 考虑其他Agent的最近行动

---

### 3. 事件优化改进 (Refine Events)

**文件位置**: `backend/workflows/event_generation.py:273-292`

**使用场景**:
- 质量验证未达标（overall_score < 0.85）
- 自动触发迭代优化（最多3次）

**触发时机**: validate_quality节点检测到质量问题

**Prompt模板**:
```python
"""以下事件存在质量问题，请改进。

【原始事件】
{draft_events}

【发现的问题】
{issues}

【改进要求】
1. 如果类型不够多样: 确保4个选项类型完全不同（military, diplomatic, economic, political各一个）
2. 如果一致性不足: 检查year={year}, month={month}, country={country}是否正确
3. 如果历史准确性不足: 调整likelihood评分，使其更符合历史实际

保持其他高质量的部分不变。

{format_instructions}

直接输出改进后的JSON。
"""
```

**输入参数**:
- `draft_events`: 原始生成的事件（JSON格式）
- `issues`: 质量问题列表（字符串数组）
  - "格式不完整或不规范"
  - "选项类型不够多样，存在重复类型"
  - "时间或国家信息不一致"
  - "历史可能性评分不合理"
- `year`, `month`, `country`: 验证参数

**质量检测逻辑**:
```python
# 4个维度评分
format_valid:          len(branches) == 4 ? 1.0 : count/4.0
diversity:             unique_types / 4.0  (期望4种不同类型)
consistency:           year/month正确性检查
historical_accuracy:   avg(likelihood) 在 0.3-0.8 之间

# 综合得分
overall_score = (format_valid + diversity + consistency + historical_accuracy) / 4
```

---

## AI决策类Prompt

### 4. AI国家决策选择 (AI Decision Maker)

**文件位置**: `backend/ai/decision_maker.py:30-76`

**使用场景**:
- AI控制的国家需要从4个选项中选择1个
- 考虑Agent性格、战略目标、当前态势

**触发时机**: 每回合决策阶段，AI Agent自动决策

**Prompt模板**:
```python
"""
你是{country_name}的最高决策者AI。

【当前态势】
时间: {year}年{month}月
军事实力: {military_power}
经济实力: {economic_strength}
外交点数: {diplomatic_points}

【外交关系】
{diplomatic_relations}

【战略目标】
{objectives}

【性格特征】
激进度: {aggression} (0-1, 越高越倾向军事行动)
外交倾向: {diplomacy} (0-1, 越高越倾向外交手段)
经济重视度: {economic_focus} (0-1, 越高越重视经济发展)
风险承受度: {risk_tolerance} (0-1, 越高越敢冒险)

【可选行动】
{options}

【评估标准】
1. 目标契合度: 行动是否有助于实现战略目标
2. 风险评估: 行动的潜在风险是否在承受范围内
3. 时机判断: 当前是否是执行该行动的最佳时机
4. 国际影响: 行动对外交关系的影响
5. 资源消耗: 行动所需资源是否充足
6. 性格匹配: 行动是否符合Agent的性格特征

根据性格特征选择:
- 如果 aggression 高: 优先考虑 military 类型
- 如果 diplomacy 高: 优先考虑 diplomatic 类型
- 如果 economic_focus 高: 优先考虑 economic 类型

请分析每个选项，选择最优行动。

输出格式（纯JSON，不要markdown标记）:
{
  "selected_action_id": "行动ID",
  "reasoning": "选择理由（50字内）",
  "expected_outcome": "预期结果",
  "risk_level": 0.5
}
"""
```

**输入参数**:
- `country_name`: 国家名称
- `year`, `month`: 当前时间
- `military_power`, `economic_strength`, `diplomatic_points`: 资源数值
- `diplomatic_relations`: 与其他国家的关系（格式化字符串）
  ```
  与英国: -0.80 (敌对)
  与苏联: +0.20 (中立)
  ```
- `objectives`: 战略目标列表
- `aggression`, `diplomacy`, `economic_focus`, `risk_tolerance`: 性格参数
- `options`: 格式化的4个选项
  ```
  1. [military] 闪电战波兰 (ID: military_001)
     描述: 发动快速机械化进攻...
     历史可能性: 85.0%

  2. [diplomatic] ...
  ```

**输出格式**:
```json
{
  "selected_action_id": "military_001",
  "reasoning": "当前德军机械化优势明显，波兰防御薄弱，符合扩张目标",
  "expected_outcome": "快速占领波兰，巩固东线",
  "risk_level": 0.7
}
```

**决策流程**:
1. LLM分析4个选项
2. 根据性格特征加权
3. 评估6个标准
4. 返回最优选择ID
5. 后端根据ID查找对应的GameEvent

---

## 结局生成类Prompt

### 5. 结局叙事生成 (Ending Narrative)

**文件位置**: `backend/services/ending_generator.py:193-295`

**使用场景**:
- 游戏结束时生成600-900字的历史小说式叙述
- 基于战略评分判定结局类型（victory/defeat/historical）

**触发时机**:
1. 自动触发（7种条件之一满足）
2. 玩家点击"🏁 查看结局"按钮

**Prompt模板**:
```python
"""你是一位历史小说家，擅长将二战历史改编成引人入胜的故事。

【游戏过程摘要】
{game_summary}

【结局触发原因】
{trigger_reason}

【任务】
根据游戏过程，创作一段引人入胜的结局叙述（600-900字）。

【叙事结构】
1. 开篇（10%）：简短回顾已发生的关键事件
   - 不要流水账式罗列玩家选择
   - 用历史叙事的口吻概括大势

2. 主体（70%）：**重点描写从当前时点到战争结束的虚构历史进程**
   - 描述关键战役、转折点、外交博弈
   - 展现各国的命运走向
   - 使用具体的地点、人物、事件细节
   - 体现战略选择的长期影响

3. 结尾（20%）：战后世界新秩序和各国的长远命运
   - 描述战后和平条约、领土变更
   - 各国在新世界格局中的地位
   - 战争对民众和社会的深远影响

【写作风格】
- ✅ 历史小说风格，富有戏剧性和画面感
- ✅ 第三人称全知视角
- ✅ 使用具体的时间、地点、人物
- ✅ 展现战争的复杂性和人性
- ❌ 禁止使用"玩家"、"AI"、"游戏"等元词汇
- ❌ 禁止使用"第X回合"、"选择了"等游戏术语
- ❌ 禁止使用"他们决定..."这样抽象的描述
- ❌ 禁止直接引用数据（"军事力量100"）

【示例开头】
"1939年9月1日凌晨，德军装甲部队越过德波边境，闪电战的序幕由此拉开..."

【示例转折】
"然而，1941年冬天的莫斯科城下，严寒成为了德军不可逾越的天堑..."

【示例结尾】
"战争结束后，欧洲的政治版图已然改写。柏林的废墟上..."

现在，请创作结局叙述。
"""
```

**输入参数**:
- `game_summary`: 完整的游戏过程摘要，包含:
  ```
  基本信息:
  - 玩家国家: 德国
  - 游戏时长: 第4回合
  - 当前时间: 1939年12月

  战略评分:
  - 德国: 83.5分 (资源35, 外交20, 战略一致性21, 行动多样性8)
  - 英国: 45.2分 (...)
  - 苏联: 23.1分 (...)

  关键历史事件:
  1. 德国: 对英法外交施压
  2. 英国: 强化海军力量
  3. 苏联: 强化工业动员
  ...（所有回合的行动）
  ```
- `trigger_reason`: 触发原因
  - "玩家主动结算游戏（1939年12月，第4回合）"
  - "时间到达1945年5月，欧洲战场战争结束"
  - "德国军事力量降至10以下，国家濒临崩溃"
  - 等7种条件

**输出要求**:
- 长度: 600-900字
- 结构: 10% 回顾 + 70% 未来模拟 + 20% 战后
- 风格: 历史小说，具体细节，戏剧张力
- 禁忌: 游戏术语、数据、抽象描述

---

### 6. 国家后续发展生成 (Country Epilogue)

**文件位置**: `backend/services/ending_generator.py:297-357`

**使用场景**:
- 为3个国家分别生成战后发展描述
- 基于每个国家的具体表现和结局

**触发时机**: 结局生成流程的一部分

**Prompt模板**:
```python
"""你是一位历史学家，负责撰写战后各国发展史。

【{country_name}的游戏表现】
总得分: {score}分
- 资源平衡: {resource_score}分
- 外交关系: {diplomatic_score}分
- 战略一致性: {strategy_score}分
- 行动多样性: {diversity_score}分

主要行动:
{actions}

【结局背景】
{ending_context}

【任务】
为{country_name}撰写战后发展描述（100-150字）。

【要求】
1. 基于该国的实际表现和得分
2. 描述战后的政治、经济、社会状况
3. 与其他国家的关系和国际地位
4. 长远的历史影响

【风格】
- 客观、简洁
- 历史叙事口吻
- 不使用游戏术语

请撰写后续发展。
"""
```

**输入参数**:
- `country_name`: 国家名称
- `score`: 战略得分（0-100）
- `resource_score`, `diplomatic_score`, `strategy_score`, `diversity_score`: 各维度得分
- `actions`: 该国所有行动列表
- `ending_context`: 结局类型和触发原因

**输出示例**:
```
德国: 战后德国被迫接受无条件投降，领土大幅缩减。盟军占领下，
国家分裂为东西两部分。战争罪行审判持续多年，纳粹主义被彻底清算。
经济在马歇尔计划援助下逐步恢复，但民族创伤需要数代人才能愈合。

英国: 虽然站在胜利一方，但帝国的衰落已不可逆转。殖民地纷纷
独立，英镑霸权让位于美元。国内经济疲弱，配给制度延续多年。
然而，英国在战后国际秩序中仍占据重要地位，成为联合国五常之一。

苏联: 以巨大代价赢得战争，国际地位空前提升。东欧纳入势力范围，
冷战格局形成。国内工业重建迅速，但政治高压和经济僵化埋下隐患。
苏联成为与美国并立的超级大国，开启长达数十年的东西方对峙。
```

---

### 7. 关键事件提取 (Key Events Extraction)

**文件位置**: `backend/services/ending_generator.py:359-407`

**使用场景**:
- 从所有回合行动中提取最关键的5-8个事件
- 用于结局界面展示

**触发时机**: 结局生成流程的一部分

**Prompt模板**:
```python
"""你是一位历史编辑，负责梳理关键历史事件。

【所有历史行动】
{all_actions}

【任务】
从以上行动中，选出5-8个最关键的历史事件。

【选择标准】
1. 战略转折点（改变战局的重大决策）
2. 军事里程碑（重大战役、占领关键地区）
3. 外交突破（结盟、宣战、和谈）
4. 经济举措（影响战争走向的经济政策）
5. 多国互动（涉及多方的复杂事件）

【要求】
- 每个事件一句话概括（15-30字）
- 包含时间信息
- 突出因果关系和影响
- 覆盖不同类型和国家

【输出格式】
返回纯JSON数组，每项为一个字符串:
[
  "1939年9月：德国闪电战波兰，英法对德宣战",
  "1939年10月：苏德签订互不侵犯条约",
  ...
]

直接输出JSON数组，不要markdown标记。
"""
```

**输入参数**:
- `all_actions`: 所有回合的行动，格式:
  ```
  回合1 (1939年9月):
  - 德国: 对英法外交施压
  - 英国: 强化海军力量
  - 苏联: 强化工业动员

  回合2 (1939年10月):
  - 德国: 占领波兰资源区
  ...
  ```

**输出格式**:
```json
[
  "1939年9月：德军装甲部队闪击波兰，英法对德宣战",
  "1939年10月：英国加速战时工业动员，海军优势扩大",
  "1939年11月：德苏签订秘密协议，划分东欧势力范围",
  "1939年12月：苏联红军大规模集结，战略意图不明",
  "1940年初：德国占领丹麦和挪威，北欧格局改变"
]
```

---

## Prompt设计原则

### 1. 结构化设计

所有Prompt都遵循统一结构:

```
【角色定位】你是...的AI/专家
↓
【输入信息】（分类组织）
- 当前态势
- 历史背景
- 角色特征
↓
【任务说明】明确要做什么
↓
【具体要求】（编号列表）
1. 格式要求
2. 内容要求
3. 质量标准
↓
【输出格式】JSON schema或示例
```

### 2. 上下文丰富性

**多层次上下文**:
1. **历史层**: RAG检索的历史事件（5条）
2. **状态层**: 当前世界状态（资源、外交、军事）
3. **角色层**: Agent性格、目标、风险偏好
4. **互动层**: 其他Agent的最近行动

**上下文构建示例**:
```python
# 1. RAG历史
rag_results = knowledge_base.search(query, top_k=5)

# 2. 世界状态
world_context = f"""
外交关系:
  与英国: -0.80 (敌对)
  与苏联: +0.20 (中立)

军事实力对比:
  GER: 100
  UK: 90
  USSR: 110
"""

# 3. Agent性格
personality_context = f"""
激进度: {agent.aggression}
外交倾向: {agent.diplomacy}
经济重视度: {agent.economic_focus}
风险承受度: {agent.risk_tolerance}
"""

# 4. 其他Agent行动
other_actions = f"""
【其他国家最近行动】
  UK: 强化海军力量
  USSR: 工业动员
"""

# 组合
full_context = "\n\n".join([rag_context, world_context, personality_context, other_actions])
```

### 3. 约束与引导

**明确约束**:
- ✅ 使用明确的禁止项（❌ 禁止...）
- ✅ 提供正反例（✅ 这样做 / ❌ 不要那样做）
- ✅ 量化标准（"20-80字"、"0.3-0.8"、"600-900字"）

**风格引导**:
```python
【写作风格】
- ✅ 历史小说风格，富有戏剧性和画面感
- ✅ 第三人称全知视角
- ✅ 使用具体的时间、地点、人物
- ❌ 禁止使用"玩家"、"AI"、"游戏"等元词汇
- ❌ 禁止使用"第X回合"、"选择了"等游戏术语
```

### 4. 输出格式控制

**强制JSON输出**:
1. 使用Pydantic Parser的`get_format_instructions()`
2. 明确说明"直接输出JSON，不要markdown标记"
3. 后处理清理可能的markdown代码块:
   ```python
   if content.startswith("```"):
       lines = content.split("\n")
       content = "\n".join(lines[1:-1])
   ```

**格式验证**:
- 使用Pydantic v2自动验证
- 质量评分系统（4维度 → overall_score）
- 不达标自动触发refine节点

### 5. 迭代优化机制

**LangGraph自动迭代**:
```python
# 条件判断
def should_refine(state):
    if state["quality_score"] >= 0.85:
        return "finalize"  # 质量达标
    if state["iterations"] >= 3:
        return "finalize"  # 防止无限循环
    return "refine"  # 继续优化

# 工作流
retrieve → generate → validate → [quality < 0.85?] → refine → validate
                                  [quality >= 0.85 or iter >= 3?] → finalize
```

**质量维度**:
1. `format_valid`: 格式完整性（4个选项？）
2. `diversity`: 类型多样性（4种不同类型？）
3. `consistency`: 时间国家一致性
4. `historical_accuracy`: likelihood合理性（0.3-0.8）

---

## 使用场景总结

### 场景1: 多Agent游戏开始

**流程**:
```
1. 玩家选择国家（GER/UK/USSR）
   ↓
2. 服务器创建3个CountryAgent
   - GER: aggression=0.8, diplomacy=0.3, economic_focus=0.6
   - UK: aggression=0.4, diplomacy=0.8, economic_focus=0.7
   - USSR: aggression=0.6, diplomacy=0.4, economic_focus=0.8
   ↓
3. 第一回合开始
```

**Prompt使用**:
- 并行调用 **Prompt #2 (多Agent事件生成)** × 3次
- 每个国家生成4个选项（共12个选项）
- 考虑各自的性格特征

**示例**:
```
德国（激进度0.8）:
  → 生成2个military选项 + 1个economic + 1个political

英国（外交倾向0.8）:
  → 生成2个diplomatic选项 + 1个economic + 1个military

苏联（经济重视0.8）:
  → 生成2个economic选项 + 1个military + 1个political
```

### 场景2: AI国家决策

**流程**:
```
1. 所有国家选项生成完成
   ↓
2. AI国家自动决策（UK, USSR）
   ↓
3. 等待玩家选择
```

**Prompt使用**:
- 调用 **Prompt #4 (AI决策)** × 2次（UK和USSR）
- 每个AI从自己的4个选项中选1个
- 输出决策理由和风险评估

**示例**:
```python
# 英国AI决策
AIDecisionMaker.select_best_action(
    agent=uk_agent,
    options=[opt1, opt2, opt3, opt4],  # 4个英国选项
    world_state=current_world
)

# 输出
{
  "selected_action_id": "diplomatic_002",
  "reasoning": "当前德国威胁加剧，需要巩固与盟友的关系",
  "expected_outcome": "获得美国支持，加强反德同盟",
  "risk_level": 0.3
}
```

### 场景3: 质量不达标自动优化

**流程**:
```
1. generate_draft生成初稿
   ↓
2. validate_quality检测质量
   - format_valid: 0.75（只有3个选项）
   - diversity: 0.5（2个military重复）
   - consistency: 1.0
   - historical_accuracy: 0.9
   → overall_score = 0.79 < 0.85
   ↓
3. should_refine() → "refine"
   ↓
4. refine_events调用 **Prompt #3 (事件优化)**
   ↓
5. 重新validate_quality
   → overall_score = 0.92 >= 0.85
   ↓
6. should_refine() → "finalize"
```

**优化Prompt输入**:
```python
{
  "draft_events": "...(原始JSON)...",
  "issues": [
    "格式不完整或不规范",
    "选项类型不够多样，存在重复类型"
  ],
  "year": 1939,
  "month": 9,
  "country": "GER"
}
```

### 场景4: 玩家主动查看结局

**流程**:
```
1. 玩家点击"🏁 查看结局"按钮
   ↓
2. 前端发送POST /api/multi-agent/simulate-ending
   ↓
3. 后端EndingGenerator计算战略得分
   - 德国: 83.5分
   - 英国: 45.2分
   - 苏联: 34.6分
   ↓
4. 判定结局类型
   - 得分差 = 83.5 - 39.9 = 43.6 > 15
   → ending_type = "victory", winner = "GER"
   ↓
5. 调用 **Prompt #5 (结局叙事)** 生成600-900字叙述
   ↓
6. 调用 **Prompt #6 (国家后续)** × 3 生成各国epilogue
   ↓
7. 调用 **Prompt #7 (关键事件)** 提取5-8个关键事件
   ↓
8. 返回完整GameEnding对象
```

**完整输出结构**:
```json
{
  "ending_type": "victory",
  "winner": "GER",
  "trigger_reason": "玩家主动结算游戏（1939年12月，第4回合）",
  "narrative": "1939年9月1日凌晨，德军装甲部队越过德波边境...(600-900字)",
  "epilogue": {
    "GER": "战后德国虽然取得了初期优势...(100-150字)",
    "UK": "英国在战争初期的犹豫...(100-150字)",
    "USSR": "苏联在观望中错失先机...(100-150字)"
  },
  "final_stats": {
    "total_turns": 4,
    "ending_time": "1939年12月",
    "scores": {
      "GER": 83.5,
      "UK": 45.2,
      "USSR": 34.6
    }
  },
  "key_events": [
    "1939年9月：德军装甲部队闪击波兰，英法对德宣战",
    "1939年10月：英国加速战时工业动员，海军优势扩大",
    ...
  ]
}
```

### 场景5: 自动触发结局（时间到达1945年5月）

**7种自动触发条件**:
```python
# 1. 时间限制
if year >= 1945 and month >= 5:
    trigger = "时间到达1945年5月，欧洲战场战争结束"

# 2. 回合限制
if current_turn >= 100:
    trigger = "游戏达到最大回合数限制"

# 3. 军事崩溃
if any_country_military < 10:
    trigger = "XX国军事力量降至10以下，国家濒临崩溃"

# 4. 经济崩溃
if any_country_economic < 10:
    trigger = "XX国经济崩溃，无法继续战争"

# 5. 霸权确立
if any_country_military > 200:
    trigger = "XX国军事霸权确立，其他国家无力抵抗"

# 6. 全面战争
if all_relations < -0.8:
    trigger = "三国全面交战，战火席卷整个欧洲"

# 7. 外交孤立
if sum(relations) < -1.5:
    trigger = "XX国完全孤立，面临多国围攻"
```

**流程**:
```
每回合结算后:
  ↓
TurnManager._check_game_ending()
  ↓
检测7种条件
  ↓
[条件满足] → 自动触发结局生成
  ↓
使用相同的Prompt #5/#6/#7
  ↓
返回TurnResult.is_game_over = True
```

---

## 附录：完整的Pydantic输出Schema

### BranchOptions Schema
```python
class BranchOptions(BaseModel):
    branches: List[GameEvent] = Field(
        description="4个可选的分支事件",
        min_length=4,
        max_length=4
    )
    reasoning: str = Field(
        description="为什么生成这些选项",
        min_length=10
    )
    generation_metadata: Optional[Dict[str, Any]] = Field(
        description="生成元数据（迭代次数、质量得分等）",
        default=None
    )

class GameEvent(BaseModel):
    id: str = Field(description="唯一标识符")
    name: str = Field(description="事件名称", min_length=5, max_length=50)
    description: str = Field(description="事件描述", min_length=5)
    event_type: Literal["military", "diplomatic", "economic", "political"]
    year: int = Field(ge=1939, le=1945)
    month: int = Field(ge=1, le=12)
    likelihood: float = Field(
        description="历史可能性（0.0-1.0）",
        ge=0.0,
        le=1.0
    )
```

### QualityMetrics Schema
```python
class QualityMetrics(BaseModel):
    format_valid: float = Field(ge=0.0, le=1.0)
    diversity: float = Field(ge=0.0, le=1.0)
    consistency: float = Field(ge=0.0, le=1.0)
    historical_accuracy: float = Field(ge=0.0, le=1.0)

    @property
    def overall_score(self) -> float:
        return (
            self.format_valid +
            self.diversity +
            self.consistency +
            self.historical_accuracy
        ) / 4.0
```

### GameEnding Schema
```python
class GameEnding(BaseModel):
    ending_type: str = Field(
        description="结局类型：victory/defeat/draw/historical"
    )
    winner: Optional[str] = Field(
        description="胜利者国家代码",
        default=None
    )
    trigger_reason: str = Field(
        description="结局触发原因"
    )
    narrative: str = Field(
        description="结局故事叙述（600-900字）",
        min_length=600,
        max_length=1000
    )
    epilogue: Dict[str, str] = Field(
        description="各国的后续发展（每国100-150字）",
        default_factory=dict
    )
    final_stats: Dict[str, Any] = Field(
        description="最终统计数据",
        default_factory=dict
    )
    key_events: List[str] = Field(
        description="关键历史事件回顾（5-8个）",
        default_factory=list,
        min_length=5,
        max_length=8
    )
```

---

## 版本历史

**v2.0 (2026-01-02)**:
- ✅ 添加多Agent事件生成Prompt（考虑性格特征）
- ✅ 添加AI决策Prompt
- ✅ 添加结局生成相关3个Prompt
- ✅ 完善质量优化迭代机制
- ✅ 添加完整使用场景说明

**v1.0 (2025-12)**:
- 初始版本，仅基础事件生成Prompt

---

**文档结束**
