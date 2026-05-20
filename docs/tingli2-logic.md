# tingli2.html 用户逻辑全解析

## 一、整体架构

### 1.1 页面结构（5个Tab页）

| Tab | 功能 | 核心内容 |
|-----|------|---------|
| 🏠 首页 | 听力统计 + 今日待复习 + 快速开始 | 统计面板、待复习预览（最多5篇）、快速开始按钮 |
| 📖 待复习 | 今日待复习完整列表 | 全部待复习短文，逐篇进入练习 |
| 📚 短文库 | 分类筛选 + 搜索 + 短文列表 | 分类标签、搜索框、短文卡片（含练习次数+复习状态） |
| ⚙️ 管理 | 短文CRUD + 导入导出 | 添加/编辑/删除短文、JSON/CSV导入导出 |
| 👤 个人 | 学习数据 + 语音设置 + 预生成 + 重置 | 星星数、已学习/待复习/已掌握、TTS设置 |

### 1.2 弹窗结构（4个弹窗）

| 弹窗 | 触发方式 | 用途 |
|------|---------|------|
| 单篇听力弹窗 | 点击任何"🎧"按钮 | 自由练习，单篇精听 |
| 批量听力弹窗 | 首页"听3/5/10篇" | 听力考试，逐题推进 |
| 考试结果弹窗 | 批量完成自动弹出 | 展示每题得分、正确率、奖励 |
| 短文编辑弹窗 | 管理页"添加/编辑" | 短文增删改 |

### 1.3 三种练习模式（全局模式切换栏）

| 模式 | 交互方式 | 适用场景 |
|------|---------|---------|
| 🗣️ 拼读 pronunciation | 看原文→听标准发音→录音→AI打分 | 口语跟读训练 |
| ✏️ 填空 fillblank | 看挖空文本→填入关联单词→检查答案 | 关键词听写 |
| 🎧 听写 dictation | 听音频→盲写全文→查看答案核对 | 全文听写（默认模式） |

---

## 二、用户流程详解

### 2.1 自由练习流程（单篇弹窗）

```
点击"🎧 练习" 或 "🎧" 按钮
  ↓
openListenModal(articleId)
  ├─ 重置状态：answerRevealed=false, cleanup音视频
  ├─ 切换到用户上次使用的模式
  ├─ 显示弹窗
  └─ 300ms 后自动播放音频（非拼读模式）
       ↓
【听写模式】
  音频播放完毕 → onFinished → addShowAnswerButton()
    → 底部出现"👁️ 查看答案"按钮
    → 用户输入文字后点击"查看答案"
       ├─ 输入为空 → toast "✏️ 请先输入你的答案"
       └─ 有输入 → revealAnswer() 展示原文+评分
              → 按钮变"🙈 隐藏答案"（toggle）
    → 用户点击"✅ 完成复习" → completeListening()
       → recordProgress(articleId, true)
       → +5⭐
       → 关闭弹窗 → renderAll()

【填空模式】
  显示挖空文本 → 用户填空 → 点击"✅ 检查答案"
    → checkFillAnswers() 标记对错 → 显示结果

【拼读模式】
  显示原文 → 点击"🔊 听标准发音" → PronunciationPlayer播放+高亮
    → 点击"🎙️ 录音" → 录制 → 再次点击停止
    → 自动上传评分 → 显示流利度/音素准确率
```

### 2.2 批量考试流程

```
首页点击"🎧 听3/5/10篇"
  ↓
startQuickListen(count)
  ├─ 从短文库随机抽取 count 篇
  ├─ 打开批量弹窗
  └─ renderBatchQuestion()
       ↓
每题流程：
  ├─ 显示进度 "1/10"
  ├─ 300ms 后自动播放音频
  ├─ 用户输入/填空/拼读
  ├─ 点击"✅ 提交并下一题" → submitBatchAnswer()
  │    ├─ 听写模式：比较单词相似度 ≥80% → correct=true
  │    ├─ 填空模式：checkFillAnswers() → pct≥60% → correct=true
  │    └─ 拼读模式：直接下一题
  ├─ 或点击"跳过" → skipBatchAnswer() → correct=false
  └─ batchIndex++ → renderBatchQuestion()
       ↓
全部完成 → finishBatch()
  ├─ 逐题 recordProgress(a.idx, a.correct)
  ├─ 计算星星奖励
  ├─ closeBatchModal()
  └─ showBatchResult() → 考试结果弹窗
```

---

## 三、练习次数逻辑

### 3.1 数据结构

```javascript
// 用户数据存储在 localStorage，key = "wuserA" 或 "wuserB"
{
  listeningTotal: 0,        // 总听力练习次数（每次+1）
  stars: 0,                 // 星星
  tingli: {
    learn: [],              // 已学习（首次正确）的文章ID列表
    done: [],               // 已掌握（复习完成全部轮次）的文章ID列表
    log: {                  // 间隔重复日志
      [articleId]: { t: timestamp, c: count, next: nextTimestamp }
      // t = 首次正确时间
      // c = 正确次数（复习第几轮）
      // next = 下次应复习的时间戳
    },
    listeningLog: {         // 纯统计日志
      [articleId]: { count: N, lastTime: timestamp }
      // count = 该文章累计练习次数
    },
    dailyLog: {             // 每日统计
      "2026-05-20": { learn:0, review:0 }
    },
    wordMode: 'fillblank',  // 练习模式偏好
    voice: 'af_sarah',      // TTS声音
    ttsSpeed: 85,           // TTS语速
    ttsModel: 'kokoro'      // TTS模型
  }
}
```

### 3.2 "练习次数"展示逻辑

**短文库列表** 中每篇短文显示 `练习N次`，来源：

```javascript
// renderArticleList() 第2011行
let log = (u.tingli?.listeningLog || {})[a.id];
let lc = log ? log.count : 0;
// 显示：练习${lc}次
```

**统计含义**：`listeningLog[articleId].count` 是该篇文章被练习的总次数，无论正确与否都+1。

**增加时机**：`recordProgress()` 被调用时：
- 单篇练习完成：`completeListening()` → `recordProgress(articleId, true)`
- 批量考试完成：`finishBatch()` → 遍历 `batchAnswers` → `recordProgress(a.idx, a.correct)`

```javascript
function recordProgress(articleId, correct) {
    u.listeningTotal += 1;                                    // 全局练习次数+1
    u.tingli.listeningLog[idx].count += 1;                   // 该文章练习次数+1
    if (correct) {
        u.tingli.log[idx].c += 1;                            // 正确次数+1（推动复习进度）
        u.tingli.log[idx].next = nextDate(now, c);           // 计算下次复习时间
    }
    u.tingli.dailyLog[today].review++;                        // 今日复习次数+1
}
```

**注意**：`listeningTotal` 和 `listeningLog.count` 在每次 recordProgress 时都+1（不管 correct 与否），而 `log.c` 只在 correct 时+1。

---

## 四、间隔重复复习系统

### 4.1 艾宾浩斯周期

```javascript
const PERIOD = [0, 1, 2, 4, 7, 15, 30];
// 含义：第0次=首次学习当天，之后每隔1天、2天、4天、7天、15天、30天复习
// 共7轮（0~6），全部通过即为"已掌握"
```

### 4.2 进入复习计划的触发

**核心机制**：用户在自由练习或批量考试中，对某篇文章**首次正确作答**（`recordProgress(id, true)` 且之前 `log` 中无记录），该文章自动进入复习计划。

```javascript
// recordProgress() 中的关键逻辑
if (correct) {
    if (u.tingli.log[idx]) {
        // 已在复习计划中 → c+1，计算next
        u.tingli.log[idx].c += 1;
        u.tingli.log[idx].next = nextDate(now, u.tingli.log[idx].c);
    } else {
        // 不在复习计划中 → 首次加入
        if (!u.tingli.learn.includes(idx)) u.tingli.learn.push(idx);
        u.tingli.log[idx] = { t: now, c: 1, next: nextDate(now, 1) };
    }
    // 复习满7轮 → 加入"已掌握"
    if (u.tingli.log[idx].c >= PERIOD.length && !u.tingli.done.includes(idx)) {
        u.tingli.done.push(idx);
    }
}
```

**没有独立的"加入复习计划"按钮**。当前逻辑是：只要对某篇文章 `recordProgress(id, true)` 被调用且 correct=true，就自动加入复习计划。

### 4.3 待复习列表进入方式

**三个入口**：

| 入口 | 位置 | 展示内容 |
|------|------|---------|
| 首页"今日待复习"卡片 | page-home | 最多显示5篇，底部提示"还有N篇..." |
| "待复习"Tab页 | page-review | 完整列表，每篇显示标题、单词、复习第N次、听力N次 |
| 个人中心"待复习"统计 | page-mine | 数字统计 |

### 4.4 今日待复习的判定逻辑

```javascript
function getReviewList() {
    let now = new Date();
    now.setHours(23, 59, 59, 999);  // 今天结束
    let todayEnd = now.getTime();
    let items = [];
    for (let idx in u.tingli.log) {
        let info = u.tingli.log[idx];
        // 条件：next存在 AND next <= 今天结束 AND 复习轮次未满
        if (info.next && info.next <= todayEnd && info.c < PERIOD.length) {
            let article = ARTICLES.find(a => a.id === parseInt(idx));
            if (article) items.push({ idx, article, info });
        }
    }
    return items;
}
```

**判定条件**：
1. 该文章在 `tingli.log` 中有记录（已加入复习计划）
2. `next` 时间戳 ≤ 今天 23:59:59
3. 正确次数 `c` < 7（未达到"已掌握"）

**举例**：
- 5月20日首次正确 → `c=1, next=5月21日`
- 5月21日待复习列表中出现该文章
- 5月21日再次正确 → `c=2, next=5月23日`
- 5月22日待复习列表中**不出现**（next是5月23日）

### 4.5 短文库列表中的状态标签

```javascript
// renderArticleList() 中的状态判定
if (reviewInfo) {
    let isMastered = reviewInfo.c >= PERIOD.length;       // c >= 7
    let nextD = reviewInfo.next ? new Date(reviewInfo.next) : null;
    if (isMastered)
        statusHtml = '✅ 已掌握';                          // 绿色
    else if (nextD && nextD <= new Date().getTime())
        statusHtml = '📌 待复习';                          // 红色
    else
        statusHtml = `复习${reviewInfo.c}/${PERIOD.length-1}`; // 灰色 "复习2/6"
}
```

| 状态 | 条件 | 显示 |
|------|------|------|
| 无标签 | 未练习过（log中无记录） | 不显示 |
| 复习N/6 | 已练习但未到复习日 | 灰色 |
| 📌 待复习 | next ≤ 当前时间 且 c < 7 | 红色 |
| ✅ 已掌握 | c ≥ 7 | 绿色 |

---

## 五、听力统计逻辑

### 5.1 首页统计面板

| 统计项 | 数据来源 | 含义 |
|--------|---------|------|
| 听力练习次数 | `u.listeningTotal` | 所有文章的练习总次数（每次recordProgress +1） |
| 练习短文数 | `Object.keys(u.tingli.listeningLog).length` | 至少练习过1次的不同文章数 |
| 已学习 | `u.tingli.learn.length` | 首次正确作答过的文章数 |
| 已掌握 | `u.tingli.done.length` | 复习满7轮的文章数 |

### 5.2 个人中心统计

| 统计项 | 数据来源 | 含义 |
|--------|---------|------|
| 已学习 | `u.tingli.learn.length + ' 篇'` | 同首页"已学习" |
| 待复习 | `countWait(u)` | next ≤ 明天结束 且 c < 7 的文章数 |
| 已掌握 | `u.tingli.done.length + ' 篇'` | 同首页"已掌握" |
| 听力练习次数 | `u.listeningTotal` | 同首页 |
| 听力练习短文数 | `Object.keys(u.tingli.listeningLog).length` | 同首页 |
| ⭐ 星星 | `u.stars` | 累计获得星星数 |

### 5.3 统计触发时机

所有统计数据在 `renderAll()` 中刷新，以下时机会触发：
- 切换Tab页
- 关闭弹窗
- 切换用户
- 完成/提交练习
- 导入/增删短文

---

## 六、得分奖励逻辑

### 6.1 星星获取

| 场景 | 星星变化 | 触发 |
|------|---------|------|
| 单篇完成复习 | +5⭐ | `completeListening()` → `u.stars += 5` |
| 批量考试 | 按题计算 | `finishBatch()` 中的累加逻辑 |

### 6.2 批量考试星星计算

```javascript
// finishBatch() 第1771-1774行
let starReward = batchAnswers.reduce((sum, a) => {
    let base = a.mode === 'pronunciation' ? 5 : (a.mode === 'fillblank' ? 10 : 20);
    return sum + (a.correct ? base : -5);
}, 0);
u.stars += starReward;
```

| 模式 | 正确基础分 | 错误扣分 |
|------|-----------|---------|
| 🗣️ 拼读 | +5⭐ | -5⭐ |
| ✏️ 填空 | +10⭐ | -5⭐ |
| 🎧 听写 | +20⭐ | -5⭐ |
| 跳过 | 0⭐ | 不扣分（skipped=true, correct=false，但 reduce 中 base 按模式算，correct=false 所以走 -5） |

**注意**：跳过的题目 `correct=false`，也会被扣5⭐。

### 6.3 听写模式正确判定

```javascript
// submitBatchAnswer() 中
let inputWords = input.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(Boolean);
let originalWords = originalText.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(Boolean);
let matched = inputWords.filter(w => originalWords.includes(w)).length;
let pct = Math.round((matched / originalWords.length) * 100);
// pct >= 80 → correct = true
```

### 6.4 填空模式正确判定

```javascript
// checkFillAnswers() 中
let pct = total > 0 ? Math.round(correct / total * 100) : 0;
// pct >= 60 → correct = true（通过 onComplete 回调传入 submitBatchAnswer）
```

### 6.5 查看答案的评分（单篇听写）

```javascript
// revealAnswer() 中
let inputWordSet = new Set(input.toLowerCase().replace(/[^\w\s]/g, '').split(/\s+/).filter(Boolean));
let matched = wordList.filter(w => inputWordSet.has(w)).length;
let wordPct = wordList.length > 0 ? Math.round(matched / wordList.length * 100) : 0;
// 显示：wordPct% + "输入 N 词 / 关联词 matched/total / 原文 N 词"
```

**注意**：单篇"查看答案"的评分**不影响 recordProgress**，只是一个展示对比。只有点击"完成复习"时才调用 `recordProgress(id, true)`。

---

## 七、考试逻辑

### 7.1 考试入口

首页"快速开始"区域的3个按钮：
- 🎧 听3篇 → `startQuickListen(3)`
- 🎧 听5篇 → `startQuickListen(5)`
- 🎧 听10篇 → `startQuickListen(10)`

### 7.2 题目选择逻辑

```javascript
function startQuickListen(count) {
    let pool = selectedCategory
        ? ARTICLES.filter(a => a.category === selectedCategory)
        : [...ARTICLES];
    pool.sort(() => Math.random() - 0.5);  // 随机打乱
    batchArticles = pool.slice(0, Math.min(count, pool.length));
}
```

- 如果有分类筛选，只从当前分类抽取
- 随机打乱顺序
- 取前 count 篇

### 7.3 考试流程

```
逐题推进（renderBatchQuestion）
  ├─ 显示进度 "N/M" + 进度条
  ├─ 自动播放音频
  ├─ 听写模式：输入框 + 提交按钮
  ├─ 填空模式：挖空文本 + 提交按钮
  ├─ 拼读模式：看原文 + 录音 + 跳过按钮
  └─ 用户操作：
       ├─ 提交 → 计算得分 → 下一题
       └─ 跳过 → correct=false → 下一题

全部完成（finishBatch）
  ├─ 逐题 recordProgress
  ├─ 计算星星奖励
  ├─ 保存用户数据
  ├─ 关闭批量弹窗
  └─ 打开考试结果弹窗

考试结果弹窗（showBatchResult）
  ├─ 显示总正确数 + 星星奖励
  ├─ 逐题展示：状态图标、标题、模式标签、得分%、关联词、原文、用户输入
  ├─ 每题有"🔊 播放"按钮（可重新听）
  └─ "🔄 重考"按钮 → retakeBatch()
       → 用相同的文章重新考一遍
```

### 7.4 考试结果展示细节

```javascript
// showBatchResult() 中每题的展示
let pctColor = pct >= 80 ? '#43a047' : pct >= 60 ? '#ffa726' : '#ef5350';
let statusIcon = a.correct ? '✅' : (a.skipped ? '⏭️' : '❌');
// 背景：正确=#f0faf4(浅绿), 错误=#fff5f5(浅红)
```

---

## 八、双用户系统

### 8.1 用户切换

```javascript
let user = "A";  // 默认用户A
function toggleUser() {
    user = user === "A" ? "B" : "A";
    document.getElementById("user-btn").textContent = "同学" + user;
    renderAll();  // 重新渲染所有数据
}
```

- 数据隔离：`localStorage key = "wuser" + user`（wuserA / wuserB）
- 右上角按钮切换，显示"同学A"或"同学B"
- 切换后所有统计、复习列表、星星都切换到对应用户

---

## 九、数据存储

### 9.1 存储位置

| 数据类型 | 存储方式 | Key |
|---------|---------|-----|
| 短文内容 | IndexedDB | MoringReadDB → articles store |
| 用户学习数据 | localStorage | wuserA / wuserB |
| TTS缓存状态 | localStorage | tts_cache |
| 音频文件缓存 | 服务端文件系统 | data/audio/*.wav |

### 9.2 默认短文

首次打开时 IndexedDB 为空，自动插入30篇默认短文（DEFAULT_ARTICLES）：
- ID 1-10：英文诗歌/韵文（分类：自然、经典、生活）
- ID 11-30：简单英语句子（分类：English）

---

## 十、关键函数索引

| 函数 | 行号 | 作用 |
|------|------|------|
| `recordProgress(articleId, correct)` | 632 | 记录练习进度，驱动间隔重复 |
| `getReviewList()` | 1945 | 获取今日待复习列表 |
| `openListenModal(articleId)` | 1617 | 打开单篇练习弹窗 |
| `closeListenModal()` | 1655 | 关闭单篇弹窗 |
| `completeListening()` | 1675 | 单篇完成复习 |
| `addShowAnswerButton()` | 1588 | 音频播完添加"查看答案"按钮 |
| `revealAnswer(cfg)` | 1424 | 显示答案+评分 |
| `startQuickListen(count)` | 1669 | 启动批量考试 |
| `submitBatchAnswer()` | 1737 | 批量提交当前题 |
| `skipBatchAnswer()` | 1763 | 跳过当前题 |
| `finishBatch()` | 1770 | 批量考试结束 |
| `showBatchResult(correctCount, starReward)` | 1835 | 展示考试结果 |
| `retakeBatch()` | 1880 | 重考 |
| `switchMode(mode)` | 1892 | 切换练习模式 |
| `renderAll()` | 2186 | 全量渲染刷新 |
| `safeUser(u)` | 613 | 安全合并用户数据（含迁移逻辑） |
| `nextDate(st, count)` | 630 | 计算下次复习时间 |

---

## 十一、待改进/潜在问题

1. **无"加入复习计划"按钮**：当前逻辑中，只要 `recordProgress(id, true)` 且首次正确就自动加入。如果用户只是随意听一听不想加入复习计划，没有办法退出。
2. **单篇"查看答案"不触发 recordProgress**：只有点"完成复习"才记录，如果用户看完答案直接关闭弹窗，这次练习不会被统计。
3. **跳过也扣星星**：批量考试中跳过题目 `correct=false` 导致 -5⭐，对用户不太友好。
4. **单篇听写评分与 recordProgress 脱节**：查看答案的 wordPct 只是展示，不影响"完成复习"的 correct 判定（固定 true）。
5. **无复习失败机制**：待复习列表中点进去做题，无论做对做错都调用 `recordProgress(id, true)`（因为"完成复习"固定 correct=true），间隔重复永远不会倒退。
