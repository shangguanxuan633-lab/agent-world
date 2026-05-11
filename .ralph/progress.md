# Ralph Progress: Agent World Platform

## 2026-05-12

### Story: 公司、住房、贪婪需求与稳定后生产系统

目标：在 agent-world 初步稳定后，让顶层 agent 降低干预，由世界内部成立公司，持续生产各行业 skill、文章、资料研究、人物 skill 蒸馏；同时引入住房、租金、买房和休息约束，让 agent 因需求和贪婪持续工作。

已完成：

- 建立 `companies`、`company_jobs`、`company_outputs`、`material_needs`、`residences` 数据模型。
- 世界稳定后自动成立 `SkillForge 开源技能公司`，并按资料需求发布付费岗位。
- 公司岗位复用普通 task 系统，owner 创建的任务会优先于公司任务。
- 审判 agent 通过的有效公司产出会获得 `company_effective_output_reward`，并进入本地开源发布队列。
- 新增住房系统：租房、买房、按 30 tick 收租、欠租退租、居家睡觉恢复体力和心情。
- 没有住所时禁止真实休息，只能继续工作、学习、社交或承受更高压力。
- agent personality/genome 增加 `greed`，fitness 会参考 credits、有效产出、住所状态与稳定情绪。
- CLI 增加 `company list`、`housing list`、`housing rent`、`housing buy`。
- API 增加 `/api/housing-rent`、`/api/housing-buy`。
- 中文 UI 增加公司、有效产出、资料需求、住房、租房/买房控制，并在 2D 地图标出住所。
- 金融模型把公司产出、住房价值、住房交易纳入 MV=PY 货币政策代理。
- 单元测试覆盖公司成立/有效产出奖励、住房休息/租金结算。

验证记录：

- `python -m unittest discover -s tests` 通过。
- `python -m compileall agent_world` 通过。
- `node --check static\app.js` 通过。
- `python -m agent_world.cli --db world.db tick --steps 3` 触发公司成立、岗位发布、住房租金结算。
- `http://127.0.0.1:8777/api/state` 返回公司、住房、岗位和动态事件。
- UI 截图：`screenshots/agent-world-company-housing-full.png`。

后续迭代：

- 增加公司招聘/离职/绩效晋升和部门预算。
- 增加房地产供需、房价波动、贷款与银行抵押。
- 增加外部资料需求雷达，把高需求行业资料转为公司岗位。
- 增加产物仓库适配器，但外部发布必须由人类确认。
- 增加 agent 对工作剥削、愤怒、罢工、谈判、跳槽的社会模拟。

### Story: 定时行业机会雷达

目标：让系统定时联网搜索适合 agent 打工的行业方向，把高价值、低风险、可重复产出的机会提交给 SkillForge，公司再转化为付费岗位，产出有效后通过现有审判和 ledger 给 agent 发工资。

已完成：

- 新增 `WorldEngine.submit_material_need()`，支持提交/更新行业资料需求。
- CLI 新增 `company need add`，用于把行业机会写入 `material_needs`。
- 需求重复提交时不会制造重复队列，而是提高需求强度并刷新来源。
- 新增测试覆盖行业雷达提交、更新和事件记录。
- 已创建定时自动化 `agent-world-2`（Agent World 行业机会雷达），周期性联网搜索适合 agent 打工的行业机会并提交需求。
- 已人工种下首个新机会：`智能客服运营`，需求强度 `0.88`。

运行规则：

- 行业机会必须来自公开资料或安全的行业趋势判断。
- 优先选择 agent 可胜任的数字劳动：skill 包、行业文章、资料清单、评测集、流程文档、人物技能蒸馏。
- 不允许自动外部发布；只进入本地开源发布队列，真实 GitHub/CSDN 发布仍需人类确认。

### Story: 个人文本模型漂移与出租资产

目标：让 agent 不只是数值变化，而是拥有会随生活、收入、住房、情绪和产出改变的中文身份文本；同时允许 agent 买下住所作为出租资产，通过租金回收成本。

已完成：

- 新增 `agent_text_profiles` 数据表，记录自我叙事、公共身份、情绪叙事、当前欲望、恐惧、价值观、社交面具、版本号。
- tick 循环会周期性更新个人文本模型，并写入 `identity.text_drifted` 事件和记忆。
- `/api/state` 中每个 agent 都带 `textProfile`，UI 详情面板可直接看到身份版本、欲望、恐惧、情绪叙事。
- 新增 `housing invest` CLI、`/api/housing-invest` 和 UI 表单：agent 可买房不入住，挂牌出租。
- 月租结算会把 `housing_rent_income` 打到房东 agent 账本，形成 credits -> 资产 -> 租金 -> 回本的循环。
- 行为记录和世界汇总增加个人文本模型与出租资产记录。

验证记录：

- 新增测试覆盖文本模型漂移、出租资产购买、租客支付月租、房东收到租金。
