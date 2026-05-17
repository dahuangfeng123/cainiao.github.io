---
name: "moring-read-vocab"
description: "Build gamified learning web apps with spaced repetition, star rewards, dual themes, exams, and admin panel. Invoke when user asks to create any learning/study/flashcard app, vocab tool, or gamified education app."
---

# Gamified Learning App Builder

Build production-ready, gamified learning web applications using pure HTML/CSS/JS (no build tools). This skill provides a universal architecture for creating interactive study tools applicable to ANY knowledge domain — not just vocabulary.

## When to Invoke

- User wants to build ANY learning/study/education application
- User asks for flashcard, spaced repetition, or memorization tools
- User needs a gamified study app with rewards and statistics
- User requests an educational app with multi-user support and admin management
- User mentions "学习工具", "记忆工具", "背XX", "flashcard app", "study app", "learning app"
- User wants to build apps for: vocabulary, formulas, history dates, anatomy, code snippets, geography, music theory, or any knowledge domain

## Core Abstractions

This skill is built on domain-agnostic abstractions. When applying to a specific domain, map concrete concepts to these abstractions:

| Abstraction | Description | Vocab Example | History Example | Anatomy Example |
|-------------|-------------|---------------|-----------------|-----------------|
| **Knowledge Item** | The atomic unit of learning | Word | Historical Event | Body Part |
| **Attribute/Field** | Testable properties of a knowledge item | word, meaning, collins | event, date, significance | name, location, function |
| **Learning Mode** | How knowledge is tested (input→output mapping) | See word→write meaning | See event→write date | See name→write function |
| **Knowledge Boundary** | Scope/filter for knowledge items | Exam scope (CET4/6) | Era/Dynasty | Body system |
| **Learner** | The entity whose progress is tracked | Student A/B | Student A/B | Student A/B |
| **Learner Data** | All progress/state for a learner | Learning indices, stars, combo | Same structure | Same structure |
| **Assessment** | Formal evaluation with scoring | Exam | Quiz | Lab test |
| **Data Report** | Visualization of learning metrics | 30-day chart | Same | Same |
| **Metadata** | Reference info about the knowledge domain | Parts of speech table | Dynasty timeline | Body system map |
| **CRUD** | Data management operations | Admin panel | Same | Same |

## Architecture Overview

```
project/
├── index.html          # Landing page / app entry
├── learn.html          # Main learning SPA (core)
├── admin.html          # Password-protected admin panel
├── knowledge.json      # Knowledge item database
└── .trae/skills/       # Skill definitions
```

**Key principle**: Single-file SPA architecture. Each HTML file is self-contained with inline CSS and JS. No build tools, no npm, no frameworks. Just open in browser.

## Knowledge Item Schema

A generic, extensible data structure for any knowledge domain:

```javascript
// Minimal required fields
const MINIMAL_ITEM = {
    id: "unique_key",        // unique identifier
    fields: {                // testable attributes — the core of flexibility
        primary: "abandon",  // main identifier (display name)
        secondary: "v.抛弃；放弃",  // primary test target
        // add any number of domain-specific fields:
        // tertiary, category, tags, audio, image, hint, etc.
    },
    meta: {
        difficulty: 3,       // difficulty/frequency level (1-5)
        scope: ["CET4", "CET6"],  // knowledge boundary tags
    }
};

// Domain-specific examples:
// Vocabulary: { primary: "word", secondary: "meaning", difficulty: collins, scope: exam }
// History:    { primary: "event", secondary: "date", tertiary: "significance", scope: era }
// Anatomy:    { primary: "part", secondary: "function", tertiary: "location", scope: system }
// Geography:  { primary: "country", secondary: "capital", tertiary: "continent", scope: region }
// Formulas:   { primary: "formula_name", secondary: "formula", tertiary: "usage", scope: subject }
```

## Core Systems

### 1. Spaced Repetition Engine

Domain-agnostic Ebbinghaus forgetting curve:

```javascript
const PERIOD = [0, 1, 2, 4, 7, 15, 30]; // configurable intervals in days

function nextReviewDate(now, reviewCount) {
    let interval = PERIOD[Math.min(reviewCount, PERIOD.length - 1)];
    let d = new Date(now);
    d.setDate(d.getDate() + interval);
    return d.getTime();
}
```

Each knowledge item tracks per-learner: `{ t: lastReviewTime, c: reviewCount, next: nextReviewDate }`

### 2. Learning Mode System

Define modes as input→output mappings between fields:

```javascript
// Each mode maps which field to SHOW and which field to ANSWER
const LEARNING_MODES = [
    { id: 1, name: "看主写副", show: "primary", answer: "secondary", icon: "📝" },
    { id: 2, name: "看副写主", show: "secondary", answer: "primary", icon: "🔄" },
    { id: 3, name: "听音写主", show: "audio", answer: "primary", icon: "🔊" },
    // Add domain-specific modes freely:
    // { id: 4, name: "看图写名", show: "image", answer: "primary", icon: "🖼️" },
    // { id: 5, name: "看提示写全部", show: "hint", answer: "all", icon: "🧠" },
];
```

A review session requires passing ALL defined modes for a knowledge item to be marked as reviewed.

### 3. Reward System

Gamification with combo bonuses — domain-agnostic. **All reward values are configurable per learner** via `task_config` (see Section 14).

#### Default Reward Table

| Event | Default Reward | Config Key |
|-------|---------------|------------|
| Correct answer | +1 star | (hardcoded) |
| 3-hit combo | +5 bonus | (hardcoded) |
| 10-hit combo | +20 bonus | (hardcoded) |
| Learn N new items today | +30 stars | `learnReward` |
| Complete review session | +30 stars | `reviewReward` |
| Complete assessment | +20 stars | `examCompleteReward` |
| Perfect assessment (all correct) | +100 stars | `examPerfectReward` |
| Clear all wrong answers | +50 stars | `examClearReward` |

**Critical**: When `addComboStar()` modifies learner data, any subsequent `setLearnerData()` must re-read data first to avoid overwriting star counts.

#### Assessment Rewards — 3 Independent Triggers

Assessment rewards are **decoupled into 3 independent events**, each triggered separately:

| Reward | Trigger Point | When |
|--------|--------------|------|
| `examCompleteReward` | Assessment finishes | First assessment of the day |
| `examPerfectReward` | Assessment finishes with 100% correct | First assessment of the day |
| `examClearReward` | Wrong pool becomes empty (after having assessments today) | Assessment finish OR wrong-answer re-test finish |

**Why decoupled**: If a learner has wrong answers after an assessment, then clears them via re-test, the `examClearReward` must still be obtainable. The `checkWrongClearBonus()` function is called at **both** assessment completion and wrong-answer re-test completion.

```javascript
// At assessment completion:
if (firstAssessmentToday) {
    addStars(tc.examCompleteReward, 'Assessment complete!');
    if (allCorrect) addStars(tc.examPerfectReward, 'Perfect score!');
}
checkWrongClearBonus();  // checks if wrong pool is now empty

// At wrong-answer re-test completion:
checkWrongClearBonus();  // same check — may trigger examClearReward

function checkWrongClearBonus() {
    let u = getLearnerData();
    let todayExams = u.assessments.filter(s => s.date === todayKey());
    if (todayExams.length === 0) return;
    let wrongCount = Object.values(u.wrongPool).filter(w => w.status === 1).length;
    if (wrongCount > 0) return;
    let key = 'wrongClearBonus_' + learnerId + '_' + todayKey();
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, '1');
    addStars(myTaskConfig().examClearReward, 'All wrong answers cleared!');
}
```

**Anti-duplicate**: Each reward uses a localStorage key with `learnerId + date` to prevent double-claiming.

### 4. Answer Matching Engine

Pluggable matching strategy per field type:

```javascript
function checkAnswer(input, correctValue, fieldType) {
    const strategies = {
        text: (a, b) => fuzzyMatch(a, b),       // fuzzy string similarity
        exact: (a, b) => a === b,                // exact match (dates, codes)
        numeric: (a, b) => Math.abs(a - b) < 0.01, // numbers/formulas
        set: (a, b) => setOverlap(a, b),         // multiple correct answers
    };
    let strategy = strategies[fieldType] || strategies.text;
    let score = strategy(input.trim().toLowerCase(), correctValue.toLowerCase());
    return { correct: score >= 0.4, score: score };
}

function fuzzyMatch(input, correct) {
    // Remove metadata prefixes (e.g., "v.", "n.", "adj.")
    let clean = correct.replace(/^[a-z]+\.\s*/g, '').trim();
    return calculateSimilarity(input, clean);
}
```

### 5. Learner Data Model

Universal learner state — same structure for any domain:

```javascript
{
    learned: [],          // learned item indices
    mastered: [],         // mastered item indices
    completed: [],        // fully completed item indices
    reviewLog: {},        // per-item review log { idx: { t, c, next } }
    dailyLog: {},         // daily stats { "2026-05-09": { learn: N, review: N } }
    assessments: [],      // assessment/exam history
    wrongPool: {},        // wrong answers { idx: { status: 1|0, c: count, pass: 0-3, date } }
    stars: 0,             // reward points
    combo: 0,             // current combo streak
    prizes: [],           // earned prizes [{ emoji, name, date }]
    milestone: 0,         // learning milestone
    lastTodayMilestone: {}, // per-day milestone record { dateKey: milestoneCount }
    preferences: {},      // learner-specific settings
    lotteryRedeemUnlock: null,  // { time: timestamp, used: boolean } 兑奖解锁抽奖资格
    lotteryLog: [],       // lottery/redeem logs [{ type, emoji, name, stars, date }]
    listeningTotal: 0,    // 听力练习总次数
    listeningLog: {},     // 听力练习记录 { idx: { count, lastTime } }
}
```

**wrongPool entry structure**:
- `status`: 1 = active wrong answer, 0 = mastered (cleared via re-test)
- `c`: number of times this item was answered wrong
- `pass`: consecutive correct re-test count (0-3, at 3 → status changes to 0)
- `date`: timestamp when wrong answer was recorded

### 6. Knowledge Boundary System

Filter knowledge items by scope tags:

```javascript
// Items have scope tags, learner selects active boundary
function filterByScope(items, activeScopes) {
    if (!activeScopes || activeScopes.length === 0) return items;
    return items.filter(item => {
        let tags = item.meta.scope || [];
        return activeScopes.some(s => tags.includes(s));
    });
}

// Examples:
// Vocabulary: scope = ["CET4", "CET6", "GRE", "TOEFL"]
// History: scope = ["秦朝", "汉朝", "唐朝", "宋朝"]
// Anatomy: scope = ["骨骼系统", "肌肉系统", "神经系统"]
```

### 7. Assessment System

- Random item selection with configurable count
- Timer with optional audio cues
- Wrong answers auto-collected to wrong pool
- Score calculation and history tracking
- Assessment reward limited to once per day

### 8. Wrong Answer Pool

- Auto-collect wrong answers during assessments and reviews
- Re-test feature with shuffled order
- N consecutive correct answers removes from pool (configurable, default 3)
- Clear all wrong answers = bonus reward

### 9. Lottery & Prize System

Dual-acquisition prize system: **random lottery** (probability-based) + **direct redemption** (fixed star cost). Same prize pool, two ways to acquire.

#### 9.1 Prize Data Model

```javascript
const DEFAULT_LOTTERY_CONFIG = {
    cost: 50,              // 每次抽奖消耗星星
    badDeduct: 30,          // "坏奖"扣减星星
    starThreshold: 5000,    // 抽奖积分门槛
    dailyLimit: 1,          // 每日抽奖次数上限
    dailySpendLimit: 500,   // 每日抽奖消耗星星上限
    redeemUnlock: true,     // 是否需要先兑奖解锁抽奖资格
    prizes: [
        { emoji:'🏆', name:'大奖', weight:1, type:'good', cost:30000 },
        { emoji:'🎁', name:'中奖', weight:5, type:'good', cost:2000 },
        { emoji:'⭐', name:'小奖', weight:10, type:'good', cost:500 },
        { emoji:'💨', name:'什么也没有', weight:40, type:'neutral', cost:0 },
        { emoji:'😈', name:'扣分', weight:44, type:'bad', cost:0 },
    ],
    wishPrize: { emoji:'🌟', name:'心愿大奖', cost:30000 }
};
```

**Prize types**:
- `good` — 实物奖品，可抽奖也可兑换
- `neutral` — 空奖，仅抽奖出现，不可兑换
- `bad` — 惩罚奖，仅抽奖出现，扣减星星，不可兑换

**Wish Prize**: 特殊奖品，**仅兑换**（不可被抽中），高星价激励长期积累。

#### 9.2 Lottery Eligibility (Multi-Gate Check)

抽奖前实时检查，所有条件必须同时满足：

| 条件 | 字段 | 说明 |
|------|------|------|
| 积分门槛 | `starThreshold` | 星星须达门槛，否则按钮灰显+显示"还差XX积分" |
| 兑奖解锁 | `redeemUnlock` | 需先完成一次兑奖解锁抽奖资格（1次/天，不叠加） |
| 每日次数 | `dailyLimit` | 当日已抽次数 < 上限 |
| 每日消耗 | `dailySpendLimit` | 当日抽奖消耗星星累计 < 上限 |
| 积分足够 | `cost` | 当前星星 >= 单次抽奖消耗 |

```javascript
function getLotteryEligibility() {
    let u = getLearnerData();
    let config = getLotteryConfig();
    let today = todayKey();
    let todayCount = (u.lotteryLog || []).filter(l => l.date === today && l.type === 'lottery').length;
    let todaySpend = (u.lotteryLog || []).filter(l => l.date === today && l.type === 'lottery').reduce((s, l) => s + (l.stars || 0), 0);
    let redeemUsed = u.lotteryRedeemUnlock && u.lotteryRedeemUnlock.date === today && u.lotteryRedeemUnlock.used;

    return {
        canLottery: u.stars >= config.starThreshold
            && (!config.redeemUnlock || redeemUsed)
            && todayCount < config.dailyLimit
            && todaySpend < config.dailySpendLimit
            && u.stars >= config.cost,
        starsEnough: u.stars >= config.starThreshold,
        starsNeeded: Math.max(0, config.starThreshold - u.stars),
        redeemOk: !config.redeemUnlock || redeemUsed,
        dailyCountOk: todayCount < config.dailyLimit,
        dailySpendOk: todaySpend < config.dailySpendLimit,
        costEnough: u.stars >= config.cost,
    };
}
```

**兑奖解锁逻辑**：完成任意兑奖 → `lotteryRedeemUnlock = { date: todayKey(), used: true }` → 当日获得1次抽奖资格，不用则失效。

#### 9.3 Lottery Animation & Selection

```javascript
function doLottery() {
    // 1. 资格检查
    // 2. 扣减星星，消耗解锁资格
    // 3. 按权重随机选中奖索引
    let totalWeight = prizes.reduce((s, p) => s + p.weight, 0);
    let rand = Math.random() * totalWeight;
    let hitIndex = 0, cumWeight = 0;
    for (let i = 0; i < prizes.length; i++) {
        cumWeight += prizes[i].weight;
        if (rand < cumWeight) { hitIndex = i; break; }
    }
    // 4. 动画：依次高亮 lottery-item，最终停在中奖项
    // 5. 根据类型处理结果：
    //    good → 加入 prizes 列表
    //    bad  → 扣减 badDeduct 星星
    //    neutral → 无操作
    // 6. 记录 lotteryLog，刷新 UI
}
```

**动画注意**：心愿大奖(wishPrize)不参与抽奖动画，仅出现在兑换区。

#### 9.4 Unified Prize Display

抽奖池和兑换区合并展示，每个奖品同时显示：
- 抽奖概率（根据 weight 计算）
- 兑换消耗（cost 星星）
- `bad`/`neutral` 类型：兑换按钮置灰，仅可抽奖获得
- `good` 类型：两种获取方式均可

**Prize sorting**: My prizes are displayed sorted by **cost descending** (highest value first). Build a `costMap` from lottery config to look up each prize's cost:

```javascript
function renderPrizes() {
    let config = getLotteryConfig();
    let costMap = {};
    config.prizes.forEach(p => { costMap[p.emoji + p.name] = p.cost || 0; });
    if (config.wishPrize) costMap[config.wishPrize.emoji + config.wishPrize.name] = config.wishPrize.cost || 0;

    let counts = {};
    prizes.forEach((p, idx) => {
        let key = p.emoji + p.name;
        if (!counts[key]) counts[key] = { emoji: p.emoji, name: p.name, count: 0, cost: costMap[key] || 0 };
        counts[key].count++;
    });
    let sorted = Object.values(counts).sort((a, b) => b.cost - a.cost);
    // render sorted prizes...
}
```

```html
<div class="lottery-item" id="lottery-item-0">
    <div class="prize-emoji">🏆</div>
    <div class="prize-name">大奖</div>
    <div class="prize-prob">1%</div>
    <div class="prize-cost">30000⭐</div>
</div>
```

#### 9.5 Prize Redemption

选中奖品 → 点击兑换按钮 → 扣减星星 → 获得奖品：

```javascript
function redeemPrize(prizeIndex) {
    let u = getLearnerData();
    let config = getLotteryConfig();
    let prize = config.prizes[prizeIndex];
    if (prize.type !== 'good') return;  // bad/neutral 不可兑换
    if (u.stars < prize.cost) { toast('星星不足', 'warning'); return; }
    u.stars -= prize.cost;
    if (!u.prizes) u.prizes = [];
    u.prizes.push({ emoji: prize.emoji, name: prize.name, date: todayKey() });
    // 兑奖解锁抽奖资格
    u.lotteryRedeemUnlock = { date: todayKey(), used: false };
    setLearnerData(u);
    addLotteryLog('redeem', prize.emoji, prize.name, -prize.cost);
    renderAll();
}
```

#### 9.6 Admin Lottery Configuration

Admin 面板中可配置：
- **基础参数**：抽奖消耗、坏奖扣分、积分门槛、每日次数上限、每日消耗上限、是否需要兑奖解锁
- **奖品列表**：每个奖品的 emoji、name、weight、cost、type，支持拖拽排序
- **心愿大奖**：独立配置 emoji、name、cost
- **抽奖计算器**：输入每日获取星星数，实时计算各奖品兑换天数、中奖概率、综合期望亏损

```javascript
// 计算器核心逻辑
let badRate = prizes.filter(p=>p.type==='bad').reduce((s,p)=>s+p.weight,0) / totalWeight;
let goodRate = prizes.filter(p=>p.type==='good').reduce((s,p)=>s+p.weight,0) / totalWeight;
let evCost = -config.cost;
let evBad = -config.badDeduct * badRate;
let evTotal = evCost + evBad;
// 显示：每次期望亏损、各奖品兑换天数、概率分布
```

#### 9.7 Lottery Data Persistence

```javascript
// Learner data 中抽奖相关字段
{
    stars: 0,                          // 星星余额
    prizes: [],                        // 已获奖品 [{ emoji, name, date }]
    lotteryRedeemUnlock: null,         // { date: '2026-05-10', used: true }
    lotteryLog: [],                    // 抽奖/兑奖日志
}

// 独立 localStorage key
localStorage.setItem('LOTTERY_CONFIG', JSON.stringify(config));
```

#### 9.8 Lottery Bug Prevention

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 抽奖后按钮不锁定 | `lotterySpinning` 未在 finally 中重置 | 用 try/finally 确保 `lotterySpinning = false` |
| 抽奖后资格状态不更新 | `renderPrizes()` 调用不存在函数导致中断 | try/finally 包裹，确保 `renderLotteryEligibility()` 执行 |
| 心愿大奖被抽中 | wishPrize 参与了抽奖动画索引 | 动画索引数组排除 wishPrize |
| 兑奖解锁判断错误 | 日期比较不精确 | 使用 `todayKey()` 严格匹配日期字符串 |

### 10. Theme System

Use `data-theme` attribute on `<html>` for theme switching:

```html
<html data-theme="cartoon">  <!-- or "simple", "dark", etc. -->
```

```css
[data-theme="cartoon"] .card { background: linear-gradient(135deg, #fff5f5, #fff0f5); border-radius: 20px; }
[data-theme="simple"] .card { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
```

Theme preference persisted in `localStorage`.

### 11. Admin Panel

Password-protected with SHA-256:

```javascript
async function sha256(str) {
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}
```

CRUD operations: data overview, learner data editing, knowledge base management, raw localStorage editing, import/export.

#### Admin Per-Learner Panel

Each learner tab includes:
- **Basic data**: stars, combo, learned count, mastered count, active wrong answers, prizes
- **Task Configuration** (see Section 14): per-learner reward settings with save/reset
- **Daily log**: learning and review counts per day
- **Assessment scores**: date, mode, score, correct/total
- **Prizes**: list with delete button
- **Wrong answer pool**: index + item name + meaning + status + error count + re-test progress
- **Learned items**: index + item name + meaning, with remove button
- **Mastered items**: same structure
- **Review plan**: index + item name + meaning + review count + next review date, overdue highlighted
- **Action buttons**: edit stars, edit combo, clear wrong pool, clear prizes, reset learner

### 12. Data Report

Use Chart.js for time-series visualization:

```javascript
new Chart(ctx, {
    type: 'bar',
    data: {
        labels: last30Days,
        datasets: [
            { label: '学习', data: learnData },
            { label: '复习', data: reviewData }
        ]
    }
});
```

### 13. Metadata Reference

Domain-specific reference tables displayed as quick-lookup cards. Examples:
- Vocabulary: Parts of speech table
- History: Dynasty timeline
- Anatomy: Body system overview
- Geography: Continent/country mapping

### 14. Task Configuration System

Per-learner configurable task parameters stored in `task_config` localStorage key. This allows different learners (e.g., Student A vs Student B) to have different learning targets and reward amounts.

#### Data Model

```javascript
const DEFAULT_TASK_CONFIG = {
    learnTarget: 10,        // items to learn per milestone
    learnReward: 30,        // stars per learning milestone
    reviewReward: 30,       // stars for completing review session
    examCompleteReward: 20, // stars for completing assessment
    examPerfectReward: 100, // stars for perfect assessment
    examClearReward: 50     // stars for clearing all wrong answers
};

// Stored as: { A: { ...config }, B: { ...config } }
function getTaskConfig() {
    try {
        let c = JSON.parse(localStorage.getItem('task_config'));
        if (!c) return { A: { ...DEFAULT_TASK_CONFIG }, B: { ...DEFAULT_TASK_CONFIG } };
        return {
            A: { ...DEFAULT_TASK_CONFIG, ...(c.A || {}) },
            B: { ...DEFAULT_TASK_CONFIG, ...(c.B || {}) }
        };
    } catch { return { A: { ...DEFAULT_TASK_CONFIG }, B: { ...DEFAULT_TASK_CONFIG } }; }
}

// Get current learner's config
function myTaskConfig() {
    let all = getTaskConfig();
    return all[currentLearner] || { ...DEFAULT_TASK_CONFIG };
}
```

#### Usage in Learning Logic

```javascript
// Learning milestone: every learnTarget items → learnReward stars
let tc = myTaskConfig();
let milestone = Math.floor(todayLearnCount / tc.learnTarget);
if (milestone > lastMilestone) {
    addStars(tc.learnReward, `Learned ${milestone * tc.learnTarget} items!`);
}

// Review completion: reviewReward stars
addStars(myTaskConfig().reviewReward, 'Review complete!');

// Assessment completion: 3 independent rewards (see Section 3)
```

#### Admin Configuration UI

In the admin panel, each learner tab includes a "⚙️ Task Configuration" card with:
- Number inputs for each config field (learnTarget, learnReward, reviewReward, examCompleteReward, examPerfectReward, examClearReward)
- "Save" button → `saveTaskConfig(learnerId)`
- "Reset to Default" button → `resetTaskConfig(learnerId)`

```javascript
function saveTaskConfig(learnerId) {
    let all = getTaskConfig();
    all[learnerId] = {
        learnTarget: parseInt(document.getElementById('tc-learnTarget-' + learnerId).value) || DEFAULT_TASK_CONFIG.learnTarget,
        learnReward: parseInt(document.getElementById('tc-learnReward-' + learnerId).value) || DEFAULT_TASK_CONFIG.learnReward,
        reviewReward: parseInt(document.getElementById('tc-reviewReward-' + learnerId).value) || DEFAULT_TASK_CONFIG.reviewReward,
        examCompleteReward: parseInt(document.getElementById('tc-examCompleteReward-' + learnerId).value) || DEFAULT_TASK_CONFIG.examCompleteReward,
        examPerfectReward: parseInt(document.getElementById('tc-examPerfectReward-' + learnerId).value) || DEFAULT_TASK_CONFIG.examPerfectReward,
        examClearReward: parseInt(document.getElementById('tc-examClearReward-' + learnerId).value) || DEFAULT_TASK_CONFIG.examClearReward
    };
    setTaskConfig(all);
}
```

#### Dynamic UI Display

All reminder cards, rule descriptions, and star displays must read from `myTaskConfig()` instead of hardcoded values:

```javascript
// Reminders
desc: `Learn ${tc.learnTarget} items → +${tc.learnReward}⭐`
potentialStars: tc.learnReward

// Rules display
<li>Learn every ${tc.learnTarget} new items → +${tc.learnReward}⭐</li>
<li>Complete assessment → +${tc.examCompleteReward}⭐</li>
<li>Perfect score → +${tc.examPerfectReward}⭐</li>
<li>Clear all wrong answers → +${tc.examClearReward}⭐</li>
```

## Domain Application Guide

### Applying to a New Domain — Checklist

1. **Define Knowledge Item fields**: What are the testable attributes?
2. **Define Learning Modes**: Which field→field mappings make sense?
3. **Define Knowledge Boundaries**: What scope tags to use?
4. **Define Metadata**: What reference tables help learners?
5. **Customize Answer Matching**: Which strategy per field type?
6. **Configure Task Parameters**: Set `learnTarget`, `learnReward`, `reviewReward`, `examCompleteReward`, `examPerfectReward`, `examClearReward` per learner via `task_config`
7. **Customize UI Labels**: Replace "单词" with domain term
8. **Prepare Knowledge Database**: JSON with all items

### Domain Examples

#### Vocabulary Learning
```
fields: { primary: "word", secondary: "meaning" }
modes: [看词写义, 看义写词, 听写单词]
boundaries: [CET4, CET6, GRE, TOEFL]
matching: fuzzy text (filter part-of-speech prefixes)
```

#### History Dates
```
fields: { primary: "event", secondary: "date", tertiary: "significance" }
modes: [看事件写日期, 看日期写事件, 看提示写事件]
boundaries: [秦朝, 汉朝, 唐朝, 宋朝, 明朝, 清朝]
matching: exact for dates, fuzzy for events
```

#### Math Formulas
```
fields: { primary: "formula_name", secondary: "formula", tertiary: "usage_example" }
modes: [看名称写公式, 看公式写名称, 看应用写公式]
boundaries: [代数, 几何, 三角, 微积分]
matching: exact for formulas (LaTeX), fuzzy for names
```

#### Programming Knowledge
```
fields: { primary: "concept", secondary: "code_snippet", tertiary: "explanation" }
modes: [看概念写代码, 看代码写概念, 看解释写概念]
boundaries: [JavaScript, Python, CSS, SQL]
matching: fuzzy for concepts, exact for syntax
```

## Critical Bug Prevention Patterns

### Pattern 1: Data Race in setLearnerData

**Problem**: Reading learner data before `addComboStar()`, then saving old data after, overwrites star updates.

**Solution**: Always re-read learner data after functions that modify it:

```javascript
// WRONG
let u = getLearnerData();
addComboStar();      // modifies and saves learner data internally
setLearnerData(u);   // overwrites with stale data!

// CORRECT
addComboStar();      // modifies and saves learner data internally
let u = getLearnerData();  // re-read fresh data
// modify u.wrongPool or other fields
setLearnerData(u);   // save with latest data
```

### Pattern 2: Function Scoping

**Problem**: Functions defined inside other functions are not accessible globally for onclick handlers.

**Solution**: Keep event handler functions at global scope, not nested.

### Pattern 3: recordDaily Timing

**Problem**: Calling `recordDaily` only at session end gives inaccurate daily stats.

**Solution**: Call `recordDaily('review')` on each correct answer in review sessions, `recordDaily('learn')` on each correct assessment answer, and `recordDaily('learn')` when learning new items.

### Pattern 4: Combo Reset Conditions

**Problem**: Combo not resetting on skip/wrong/view-answer breaks reward fairness.

**Solution**: Reset combo to 0 on: wrong answer, skip, view answer. Only correct answers increment combo.

### Pattern 5: Lottery Spinning Lock

**Problem**: After lottery animation, button stays locked (`lotterySpinning = true`) if callback throws error.

**Solution**: Wrap lottery callback in try/finally to ensure `lotterySpinning` is always reset:

```javascript
let interval = setInterval(() => {
    currentStep++;
    if (currentStep >= steps) {
        clearInterval(interval);
        try {
            // 处理中奖结果、更新UI
        } catch(e) {
            console.error('lottery callback error:', e);
        } finally {
            renderLotteryEligibility();
            updateRedeemBtn();
            lotterySpinning = false;  // 必须重置
        }
    }
}, 80);
```

### Pattern 6: Lottery UI State After Draw

**Problem**: After drawing, eligibility display and button state don't update because `renderPrizes()` calls a non-existent function, causing ReferenceError that breaks subsequent code.

**Solution**: Ensure all render functions exist, and wrap critical render calls in try/finally:

```javascript
// WRONG: renderPrizes() 内部调用不存在的 renderRedeemList() → ReferenceError → 后续代码不执行
// CORRECT: 确保所有 render 函数存在，关键状态更新放在 finally 中
try {
    renderPrizes();
    renderLotteryBox();
} catch(e) {
    console.error('render error:', e);
} finally {
    renderLotteryEligibility();  // 确保资格状态更新
    updateRedeemBtn();           // 确保按钮状态更新
}
```

### Pattern 7: Variable Declaration Order (TDZ)

**Problem**: In single-file SPAs with inline `<script>`, `let`/`const` declarations placed after function calls that reference them cause "Cannot access X before initialization" errors due to JavaScript's Temporal Dead Zone.

**Solution**: Declare all module-level variables at the **very top** of the script, before any function definitions or initialization calls:

```javascript
// WRONG: variable declared after function that uses it
function init() { console.log(cache); }  // TDZ error if called before line below
let cache = null;
init();

// CORRECT: declare first, use later
let cache = null;
function init() { console.log(cache); }  // OK
init();
```

### Pattern 8: Hardcoded Reward Values

**Problem**: Hardcoding reward values (e.g., `10` for learn target, `30` for reward stars) makes it impossible to customize per learner and requires code changes to adjust.

**Solution**: Use the Task Configuration System (Section 14) — store all configurable values in `task_config` and read via `myTaskConfig()`. Never hardcode reward amounts in business logic or UI display strings.

```javascript
// WRONG
let learnDone = todayLearn >= 10;
addStars(30, 'Learn complete!');
desc: `Learn 10 items → +30⭐`

// CORRECT
let tc = myTaskConfig();
let learnDone = todayLearn >= tc.learnTarget;
addStars(tc.learnReward, 'Learn complete!');
desc: `Learn ${tc.learnTarget} items → +${tc.learnReward}⭐`
```

### Pattern 9: Wrong Clear Bonus Must Be Independently Triggerable

**Problem**: If wrong-answer-clear bonus is only checked at assessment completion, learners who clear wrong answers via re-test after the assessment will never receive the bonus.

**Solution**: Extract `checkWrongClearBonus()` as a standalone function and call it at **both** assessment completion and wrong-answer re-test completion. Use a localStorage key with `learnerId + date` to prevent double-claiming.

### Pattern 10: localStorage Key Must Include Learner ID

**Problem**: Using shared localStorage keys like `'examWrongClearBonus_2026-05-13'` causes Learner A's bonus to block Learner B's bonus on the same browser.

**Solution**: Always include `learnerId` in per-learner localStorage keys: `'wrongClearBonus_A_2026-05-13'`.

## UI/UX Guidelines

- **Cartoon theme**: Rounded corners (20px), gradient backgrounds, playful colors, emoji-rich
- **Simple theme**: Clean borders, minimal shadows, green primary (#34a853), professional
- **Responsive**: Mobile-first, touch-friendly buttons (min 44px tap targets)
- **Sound feedback**: Correct/wrong/victory sounds via Web Audio API
- **Star animations**: CSS keyframe pop-up effects on star gain
- **Real-time reward display**: Show star count in all active learning/test interfaces
- **Urgency reminders**: Countdown to daily reset, star loss warnings, task completion prompts

## Technology Stack

- **Pure HTML/CSS/JS** - No build tools required
- **localStorage** - All data persistence (learner data, lottery config, task config, theme)
- **Chart.js** (CDN) - Statistics visualization
- **SheetJS/xlsx** (CDN) - Excel export
- **Web Speech API** - Text-to-speech (when applicable)
- **Web Crypto API** - SHA-256 password hashing
- **CSS Custom Properties** - Theme system

## localStorage Key Reference

| Key Pattern | Purpose |
|-------------|---------|
| `wuser{A/B}` | Learner data (shared across modules) |
| `ALL_WORDS_DATA` | Knowledge item cache |
| `lottery_config` | Lottery/prize configuration |
| `lottery_logs` | Lottery/redeem history logs |
| `task_config` | Per-learner task parameters `{ A: {...}, B: {...} }` |
| `wtheme` | Theme preference |
| `wrongClearBonus_{learnerId}_{date}` | Anti-duplicate flag for wrong-answer-clear bonus |
