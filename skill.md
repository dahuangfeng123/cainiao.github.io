# 单词复习工具 - 功能技能文档

## 项目概述
单文件 HTML 应用，基于艾宾浩斯遗忘曲线的双用户单词学习与复习系统。所有数据存储在浏览器 localStorage 中。

## 页面模块
| 模块 | 入口 | 说明 |
|---|---|---|
| 首页 | `show('home')` | 今日任务提醒、倒计时、星星奖励 |
| 复习计划 | `show('plan')` | 日历视图、今日复习列表、随机推荐 |
| 单词库 | `show('lib')` | 单词列表、分类筛选、学习/复习/熟练操作 |
| 考试 | `show('exam')` | 三种模式考试、错题重练、成绩记录 |
| 关系查询 | `show('relation')` | 词汇关系图谱搜索 |
| 个人中心 | `show('mine')` | 统计数据、错题库、考试记录、主题/语音设置、数据导入导出 |

## 用户数据结构 (`safeUser`)
```js
{
  learn: [],          // 已学习单词索引列表（含待复习和已学会）
  done: [],           // 已学会（完成全部复习周期）的单词索引
  skilled: [],        // 已熟练（手动标记，从learn/done/log中移除）
  log: {},            // 复习日志 { [idx]: { t, c, next } }
  exam: "",           // 当前选择的考试类型
  translate: false,   // 是否开启翻译
  dailyLog: {},       // 每日统计 { "2026-05-14": { learn: 0, review: 0 } }
  examScores: [],     // 考试成绩记录
  voice: "local",     // 语音设置
  wrongPool: {},      // 错题库 { [idx]: { status, c, pass, date } }
  stars: 0,           // 星星数量
  combo: 0,           // 连击数
  learnMilestone: 0,
  lastTodayMilestone: {},
  prizes: [],         // 已兑换奖品
  lotteryRedeemUnlock: null
}
```

## 核心常量
- `PERIOD = [0, 1, 2, 4, 7, 15, 30]` — 艾宾浩斯复习间隔（天），共7个阶段
- `MODE_LABELS = { 1: "看词写义", 2: "看义写词", 3: "听写单词" }` — 复习/考试模式
- `EXAM_LABELS = { zk, gk, cet4, cet6, ky, ielts, toefl }` — 考试类型标签

## 单词状态流转

```
新单词 → [学习] → learn[] + log{c:1} → 待复习
待复习 → [复习3轮通过] → log.c++ → 循环直到 c >= PERIOD.length → done[] 已学会
任意状态 → [标记熟练] → skilled[]（从learn/done/log中移除，"单词坟场"）
skilled → [取消熟练] → learn[]（回到待学习，不创建log）
```

### 筛选分类（互斥）
| 分类 | 条件 |
|---|---|
| 待学习 | 不在 learn、done、skilled 中 |
| 已复习 | 在 learn 中，不在 done、skilled 中 |
| 已学会 | 在 done 中，不在 skilled 中 |
| 已熟练 | 在 skilled 中 |

## 复习系统

### 任务复习 vs 自由复习
- **任务复习**（`startReviewSession`）：从首页"去复习"进入，`isTaskReview = true`
  - 答对加分（`addComboStar`）、记录每日复习（`recordDaily('review')`）
  - 完成后更新 log.c、log.next、发放任务奖励
- **自由复习**（`openModal`）：从单词库点击"复习"进入，`isTaskReview = false`
  - 纯练习，不加分、不记录、不更新复习周期

### 复习流程
1. `startReviewSession()` 或 `openModal(idx)` 初始化
2. `renderReviewWord()` 渲染当前单词
3. `submitReviewAnswer()` 提交答案 → 正确进入下一题，错误显示答案
4. 一轮结束 → `finishReviewRound()` → 过滤通过的单词进入下一轮
5. 三轮结束 → `finishReviewAll()` → 更新数据、发放奖励

### 首页任务完成判断
- 学习任务：`todayLearn >= tc.learnTarget`
- 复习任务：`reviewCount === 0`（无待复习单词）
- 考试任务：`todayExamScores.length > 0`

## 考试系统
- 三种模式：看词写义、看义写词、听写单词
- 答错进入 `wrongPool`，连续答对3次后 `status` 从1变为0
- 错题库显示所有曾经错过的单词，按最后出错时间倒序
- 答案匹配使用 `checkExamAnswer()`，基于字符集相似度算法

## 星星奖励系统
- 学习单词 +1⭐
- 复习答对 +1⭐ + 连击奖励（3连+5, 10连+20, 每10连+20）
- 完成学习/复习/考试任务有额外奖励
- 星星可用于抽奖和兑换奖品

## 关键函数索引
| 函数 | 位置 | 说明 |
|---|---|---|
| `toggleSkilled(idx)` | ~2846 | 标记/取消熟练，同步更新learn/done/log |
| `startReviewSession()` | ~3120 | 启动任务复习 |
| `openModal(idx)` | ~3318 | 启动自由复习 |
| `finishReviewAll()` | ~3270 | 复习完成，按isTaskReview决定是否更新数据 |
| `getTodayTasks()` | ~3659 | 获取今日待复习单词（排除done和skilled） |
| `renderWordList(forceReset)` | ~2737 | 渲染单词列表，支持true/keepPage/空三种模式 |
| `renderMyWrongList(u)` | ~3436 | 渲染个人中心错题库 |
| `renderStats()` | ~3411 | 渲染统计数据 |
| `renderToday()` | ~3461 | 渲染首页任务提醒 |

## 数据持久化
- 用户数据：`localStorage["wuserA"]` / `localStorage["wuserB"]`
- 单词数据：`words.json`（远程加载）
- 关系数据：`relations.csv`（远程加载）
- 支持导出/导入 JSON、下载 XLSX
