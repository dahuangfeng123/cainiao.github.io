# Moring_Read 项目记忆

## 项目概述

**早读动物园** -- 面向小学生的纯前端学习工具集，包含单词复习、数学公式学习、诗词背诵、英语听力练习、朗读激励等功能。所有数据存储在浏览器 localStorage / IndexedDB 中，无需后端数据库（仅听力模块使用 Flask TTS 服务）。

---

## 文件清单

| 文件 | 用途 |
|---|---|
| index.html | 早读动物园 -- 麦克风音量检测 + 动物生成激励 |
| danci.html | 单词复习工具 -- 艾宾浩斯双用户版（核心模块，~217KB） |
| math.html | 数学知识学习工具 -- 艾宾浩斯双用户版 |
| shici.html | 诗词复习工具 -- 艾宾浩斯双用户版 |
| tingli.html | 听力练习 Demo（旧版，内置短文数据） |
| tingli2.html | 听力练习（新版，IndexedDB + 完整管理） |
| admin.html | 单词模块管理后台（密码保护） |
| math-admin.html | 数学模块管理后台（密码保护） |
| fanyi.html | 纯前端英中翻译（HuggingFace Transformers 本地推理） |
| lottery_calculator.html | 抽奖积分计算器（独立分析工具） |
| main.py | Flask TTS 服务器（edge-tts，端口 5003） |
| words.json | 英语单词库（~1.6MB，含 Collins 星级、考试类型、释义） |
| math.json | 数学公式知识库 |
| shici.json | 古诗词库 |
| chaodai.json | 朝代数据 |
| hanzi.csv | 汉字数据 |
| correct.mp3 / wrong.mp3 / victory.mp3 | 音效文件 |

---

## localStorage Key 汇总

| Key | 所属模块 | 说明 |
|---|---|---|
| `wuserA` / `wuserB` | danci / tingli / tingli2 | 同学A/B 用户数据 |
| `muserA` / `muserB` | math | 数学模块同学A/B 用户数据 |
| `userA` / `userB` | shici | 诗词模块同学A/B 用户数据 |
| `ALL_WORDS_DATA` | danci | 英语单词库缓存 |
| `wtheme` | danci | 主题设置（cartoon/dark/ocean 等） |
| `lottery_config` | danci / admin | 单词模块抽奖配置 |
| `lottery_logs` | danci / admin | 单词模块抽奖日志 |
| `task_config` | danci / admin | 任务奖励配置（按用户区分） |
| `math_words` | math / math-admin | 数学知识库缓存 |
| `math_lottery_config` | math / math-admin | 数学模块抽奖配置 |
| `math_lottery_logs` | math / math-admin | 数学模块抽奖日志 |
| `poems` | shici | 诗词库缓存 |
| `zoo_history` | index | 早读动物园历史记录（最多50条） |
| `wrongClearBonus_A_` / `wrongClearBonus_B_` + 日期 | danci | 错题清零奖励防重复标记 |

---

## 用户数据结构

### danci / tingli 模块（`wuserA`/`wuserB`）

```javascript
{
    learn: [],               // 已学习单词索引列表
    done: [],                // 已完成全部复习周期的单词索引
    log: {},                 // 艾宾浩斯复习日志 { wordIndex: { st, t, c, next } }
    exam: "",                // 当前考试状态
    skilled: [],             // 已掌握的单词索引
    translate: false,        // 是否开启翻译模式
    dailyLog: {},            // 每日统计 { "2026-05-16": { learn: 0, review: 0 } }
    examScores: [],          // 考试成绩记录
    voice: "local",          // 语音设置
    wrongPool: {},           // 错题池 { idx: { status: 1|0, c: count, pass: 0-3, date } }
    stars: 0,                // 星星积分
    combo: 0,                // 连续正确次数
    learnMilestone: 0,       // 学习里程碑
    lastTodayMilestone: {},  // 今日里程碑记录 { dateKey: milestoneCount }
    prizes: [],              // 已兑换奖品列表 [{ emoji, name, date }]
    lotteryRedeemUnlock: null, // 兑奖解锁抽奖资格 { time, used }
    listeningTotal: 0,       // 听力练习总次数
    listeningLog: {}         // 听力复习日志 { articleId: { st, c, next } }
}
```

### math 模块（`muserA`/`muserB`）

```javascript
{
    learn: [], done: [], log: {}, dailyLog: {},
    examScores: [], wrongPool: {},
    stars: 0, combo: 0,
    learnMilestone: 0, lastTodayMilestone: {},
    prizes: [], lotteryRedeemUnlock: null,
    lotteryLog: [], listeningTotal: 0, listeningLog: {}
}
```

### shici 模块（`userA`/`userB`）

```javascript
{
    learn: [], done: [], log: {}, grade: "",
    skilled: [], dailyLog: {}, examScores: []
}
```

---

## 配置系统

### 抽奖配置（`lottery_config` / `math_lottery_config`）

```javascript
{
    cost: 50,              // 每次抽奖消耗星星
    badDeduct: 30,         // 坏奖扣减星星
    starThreshold: 5000,   // 抽奖积分门槛
    dailyLimit: 1,         // 每日抽奖次数上限
    dailySpendLimit: 500,  // 每日抽奖消耗上限
    redeemUnlock: true,    // 需要兑奖解锁抽奖
    prizes: [
        { emoji: '🍔', name: '汉堡', weight: 0.01, type: 'good', cost: 2000 },
        { emoji: '🍦', name: '冰激凌', weight: 0.01, type: 'good', cost: 1800 },
        { emoji: '🍗', name: '鸡腿', weight: 0.01, type: 'good', cost: 1800 },
        { emoji: '🖊️', name: '圆珠笔', weight: 0.02, type: 'good', cost: 1600 },
        { emoji: '📓', name: '记事本', weight: 0.02, type: 'good', cost: 1600 },
        { emoji: '🍭', name: '棒棒糖', weight: 0.05, type: 'good', cost: 400 },
        { emoji: '🫧', name: '泡泡糖', weight: 0.05, type: 'good', cost: 200 },
        { emoji: '💔', name: '积分减30', weight: 0.15, type: 'bad', cost: 0 },
        { emoji: '💨', name: '什么也没有', weight: 0.68, type: 'neutral', cost: 0 }
    ],
    wishPrize: { emoji: '🌟', name: '心愿大奖', cost: 30000 }
}
```

### 任务配置（`task_config`）-- 按学生独立设置

```javascript
{
    A: {
        learnTarget: 10,        // 学习目标（单词数）
        learnReward: 30,        // 学习奖励星星
        reviewReward: 30,       // 复习奖励星星
        examCompleteReward: 20, // 完成考试奖励
        examPerfectReward: 100, // 满分奖励
        examClearReward: 50     // 错题清零奖励
    },
    B: { /* 同结构 */ }
}
```

---

## 模块间关联

```
index.html (早读动物园)
  └── zoo_history (独立 localStorage)

danci.html (单词复习) ←→ admin.html (单词管理后台)
  ├── wuserA / wuserB       ←──→ tingli.html / tingli2.html (共享用户数据)
  ├── ALL_WORDS_DATA         ←── words.json
  ├── lottery_config / lottery_logs
  ├── task_config
  └── wtheme

math.html (数学学习) ←→ math-admin.html (数学管理后台)
  ├── muserA / muserB        (独立用户数据)
  ├── math_words              ←── math.json
  └── math_lottery_config / math_lottery_logs

shici.html (诗词复习)  (无管理后台)
  ├── userA / userB           (独立用户数据)
  └── poems                   ←── shici.json + chaodai.json

tingli2.html (听力练习新版)
  ├── wuserA / wuserB         (与 danci 共享 key)
  └── IndexedDB: MoringReadDB.articles

fanyi.html (翻译)     (完全独立)
lottery_calculator.html (完全独立)

main.py (Flask TTS 服务)
  └── 被 tingli.html / tingli2.html 调用 http://localhost:5003/tts
```

**关键关联**：
1. danci + tingli/tingli2 共享 `wuserA`/`wuserB`，听力字段直接写入单词模块用户数据
2. math 模块完全独立（`muserA`/`muserB` 前缀）
3. shici 模块完全独立（`userA`/`userB` 无前缀）
4. danci 和 math 各有独立抽奖配置，但结构相同
5. 仅听力模块依赖 Flask TTS 服务，其余全部纯前端

---

## danci.html 核心功能模块

### 页面结构（6页）
- 首页（今日任务 + 倒计时 + 星星显示）
- 学习页（单词库浏览 + 学习弹窗）
- 复习页（艾宾浩斯3轮复习）
- 考试页（随机抽题 + 计时 + 评分）
- 统计页（Chart.js 图表）
- 奖品页（抽奖 + 兑奖商城 + 我的奖品）

### 星星获取规则
- 每答对1题 +1⭐
- 今日学习每满 learnTarget 个新单词 +learnReward⭐
- 完成复习任务（3轮全部通过）+reviewReward⭐
- 完成考试 +examCompleteReward⭐
- 考试全对 +examPerfectReward⭐
- 错题清零 +examClearReward⭐
- 考试答错1题 -1⭐

### 连击奖励
- 连续答对3题 +5⭐（含基础1⭐共6⭐）
- 连续答对10题 +20⭐（含基础1⭐共21⭐）
- 之后每10连击额外 +20⭐

### 艾宾浩斯复习间隔
`[0, 1, 2, 4, 7, 15, 30]` 天

### 错题系统
- 考试答错 → 进入 wrongPool（status=1）
- 重考连续答对3次 → status 变为 0（掌握）
- 错题清零奖励独立触发：考试结束时 + 错题重考完成时都会检查

### 抽奖资格
- 星星 >= starThreshold（默认5000）
- 今日抽奖次数 < dailyLimit（默认1）
- 今日抽奖消耗 < dailySpendLimit（默认500）
- 需要先兑奖解锁（redeemUnlock=true 时）
- 星星 >= cost（默认50）

### 奖品排序
按 cost 从高到低排序（心愿大奖 30000 > 汉堡 2000 > ... > 泡泡糖 200）

---

## admin.html 管理后台

### 密码
SHA-256 哈希验证，存储在 `PASSWORD_HASH` 常量中。

### 7个Tab
1. 📊 总览 -- 双用户数据概览
2. 👤 A -- 同学A数据管理 + 任务配置
3. 👤 B -- 同学B数据管理 + 任务配置
4. 📚 单词库 -- 增删改查 + 导入导出
5. 🎰 抽奖配置 -- 奖品列表编辑
6. 📦 数据管理 -- 导入/导出/清空
7. 💻 原始数据 -- JSON 编辑器

### 同学面板功能
- 基本数据（星星/连击/已学习/已熟练/活跃错题/奖品数）
- ⚙️ 任务配置（学习目标/学习奖励/复习奖励/考试完成奖励/考试全对奖励/错题清零奖励）
- 每日学习记录
- 考试成绩
- 奖品列表
- 错题库（显示索引+单词+释义+状态+出错次数+重考进度）
- 已学习单词
- 已熟练单词
- 复习计划
- 操作按钮：修改星星/修改连击/清空错题/清空奖品/重置

---

## 历史修改记录

### 2026-05-13 修改

1. **admin错题库显示单词**：错题库表格新增"单词"和"释义"列，不再只显示索引
2. **admin单词库性能优化**：
   - 添加 `getWordsCached()` 缓存机制，减少 localStorage 读取
   - 添加 `invalidateWordCache()` 数据变更时清缓存
   - 分页大小从 1000 改为 50，渐进加载
   - 添加 `wordFilteredCache` 过滤结果缓存
3. **任务配置可按学生独立设置**：
   - 新增 `task_config` localStorage key
   - 新增 `DEFAULT_TASK_CONFIG` / `getTaskConfig()` / `myTaskConfig()` / `setTaskConfig()`
   - danci.html 所有硬编码值（学习目标10、奖励30⭐/50⭐/100⭐等）改为从配置读取
   - admin.html 每个学生面板新增"⚙️ 任务配置"卡片，含6个配置项
   - 新增 `saveTaskConfig()` / `resetTaskConfig()` 函数
4. **考试奖励拆分为3个独立奖励**：
   - `examCompleteReward`（默认20⭐）：完成考试即给
   - `examPerfectReward`（默认100⭐）：考试全对
   - `examClearReward`（默认50⭐）：错题清零（独立触发）
   - `checkExamAndWrongClearBonus()` 拆为 `checkWrongClearBonus()`，在考试结束和错题重考完成两处调用
   - localStorage key 从 `examWrongClearBonus_` 改为 `wrongClearBonus_` + user 区分
5. **抽奖次数用完提示**：改为"明天再来"（曾尝试倒计时但用户觉得太长）
6. **奖品按价值排序**：`renderPrizes()` 中从 lottery_config 读取 cost，按 cost 降序排列
7. **错题清零奖励防重复 key 加入 user 区分**：避免 A/B 同学互相影响
