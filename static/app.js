const state = {
  world: null,
  previousWorld: null,
  selectedAgent: null,
  activityItems: [],
  highlightAgents: new Map(),
  lastSeenEventId: 0,
  lastRefreshAt: null,
  refreshing: false,
};

const colors = {
  top_planner: "#6957a8",
  judge: "#b36b15",
  researcher: "#1f7a8c",
  engineer: "#2c7a4b",
  documentarian: "#b33a3a",
  social: "#4f6f8f",
  hybrid: "#7a5c1f",
  government: "#263035",
  bank: "#176d5d",
  guard: "#8b4f16",
  army: "#4f5f3f",
  court: "#5f4b8b",
  nuwa_perspective: "#7a5c1f",
};

const roleNames = {
  top_planner: "顶层规划",
  judge: "审判",
  researcher: "研究员",
  engineer: "工程师",
  documentarian: "文档员",
  social: "社交",
  hybrid: "混合型",
  government: "政府",
  bank: "银行",
  guard: "守卫",
  army: "防务",
  court: "法院",
  nuwa_perspective: "女娲视角",
};

const statusNames = {
  bootstrap: "启动期",
  stand_down: "自主运行",
  idle: "空闲",
  working: "工作中",
  leisure: "休闲中",
  researching: "研究中",
  training: "训练中",
  trained: "训练完成",
  proud: "自豪",
  stung: "受挫",
  reflecting: "反思中",
  incubating: "孵化中",
  done: "完成",
  open: "开放",
  in_progress: "进行中",
  active: "活跃",
  sold: "已售出",
  sold_out: "售罄",
  queued: "排队中",
  pending: "待审判",
  approved: "已通过",
  rejected: "未通过",
  settled: "已结算",
  operational: "运营中",
  resting: "居家休息",
  rented: "已出租",
  for_rent: "可租",
  for_sale: "可买",
  owner_occupied: "自住房",
  needs_revision: "需返工",
  accepted: "有效",
  allowed: "允许交易",
  regulated: "监管交易",
  prohibited: "禁止交易",
  legal: "合法",
  "regulated-approved": "监管通过",
};

const archetypeNames = {
  strategist: "战略规划者",
  critic: "严格审判者",
  scout: "知识侦察员",
  builder: "实践建造者",
  writer: "知识写作者",
  host: "社交主持人",
  "state-council-model": "制度协调者",
  "public-finance": "公共金融官",
  "public-security": "公共秩序守卫",
  defense: "应急防务官",
  "judicial-review": "法务审查者",
};

const eventNames = {
  support: "支持",
  conflict: "冲突",
  neutral: "中性",
  first_contact: "初次接触",
};

const tradeCategoryNames = {
  knowledge: "知识成果",
  "skill-training": "技能训练",
  "labor-time": "劳动时间",
  document: "文档",
  "digital-tool": "数字工具",
  product: "产品",
  building: "建筑资产",
  "construction-service": "建设服务",
  "financial-report": "金融研究报告",
  "skill-package": "技能包",
  "industry-article": "行业文章",
  "persona-distillation": "人物技能蒸馏",
  "material-research": "必需资料研究",
  housing: "住房",
  "venue-service": "场所服务",
  "compute-time": "算力时间",
  "security-service": "守卫服务",
  "defense-service": "防务服务",
  identity: "身份与人格",
  "private-data": "隐私数据",
  exploit: "漏洞或滥用",
  weapon: "不安全武器",
  "stolen-property": "非法占有物",
};

const institutionNames = {
  government: "小世界政府",
  "central-bank": "Agent Credits 银行",
  "public-security": "城市守卫署",
  defense: "应急防务部",
  court: "小世界法院",
};

const institutionMandates = {
  government: "协调公共规则、预算、市场许可和公共政策。",
  "central-bank": "维护 agent-credits 账本、结算纪律和信用市场稳定。",
  "public-security": "维护模拟世界公共秩序，标记不安全或被胁迫的交易。",
  defense: "负责模拟世界的集体防务和应急稳定，不映射现实强制力。",
  court: "审查争议、监管交易和市场活动的法律边界。",
};

const sourceNames = {
  seed: "初始种子",
  "system-seed": "系统种子",
  "autonomous-web-research": "自主网络学习",
  "peer-message": "同伴中文教学",
};

const metricNames = {
  joy: "愉悦",
  anger: "愤怒",
  stress: "压力",
  confidence: "自信",
  rest: "休息",
  social: "社交",
  fun: "开心",
  purpose: "意义感",
  safety: "安全感",
  health: "健康",
};

const canvas = document.getElementById("worldCanvas");
const ctx = canvas.getContext("2d");
const summary = document.getElementById("summary");
const refreshStatus = document.getElementById("refreshStatus");
const toast = document.getElementById("toast");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2400);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await res.json();
  if (!res.ok || payload.error) {
    throw new Error(payload.error || `HTTP ${res.status}`);
  }
  return payload;
}

async function refresh(options = {}) {
  if (state.refreshing) return;
  state.refreshing = true;
  renderRefreshStatus();
  try {
    const nextWorld = await api("/api/state");
    integrateWorld(nextWorld);
    render();
  } catch (err) {
    if (!options.silent) showToast(err.message);
    throw err;
  } finally {
    state.refreshing = false;
    renderRefreshStatus();
  }
}

function integrateWorld(nextWorld) {
  const previousWorld = state.world;
  const firstLoad = !previousWorld;
  const activities = collectActivities(nextWorld, previousWorld, firstLoad);
  const now = Date.now();
  for (const item of activities) {
    item.seenAt = now;
    for (const agentId of item.agentIds || []) {
      state.highlightAgents.set(agentId, now + 5200);
    }
  }
  const merged = new Map();
  for (const item of [...activities, ...state.activityItems]) {
    if (!merged.has(item.key)) merged.set(item.key, item);
  }
  state.activityItems = [...merged.values()].sort(sortActivities).slice(0, 80);
  state.previousWorld = previousWorld;
  state.world = nextWorld;
  state.lastSeenEventId = Math.max(state.lastSeenEventId || 0, maxId(nextWorld.events || []));
  state.lastRefreshAt = new Date();
}

function collectActivities(world, previousWorld, firstLoad) {
  const previousEventMax = previousWorld ? maxId(previousWorld.events || []) : 0;
  const events = (world.events || [])
    .filter((event) => firstLoad || Number(event.id) > previousEventMax)
    .sort((a, b) => Number(b.id || 0) - Number(a.id || 0));
  const activities = [];
  for (const event of events) {
    activities.push(...eventToActivities(event));
  }
  return firstLoad ? activities.slice(0, 28) : activities;
}

function eventToActivities(event) {
  const payload = parsePayload(event.payload_json);
  if (event.kind === "world.tick") {
    return tickToActivities(event, payload);
  }
  const actor = event.actor_agent_id || payload.agent || payload.owner || "world";
  const kindNames = {
    "task.completed": "完成任务",
    "venue.visited": "场所消费",
    "skill.autonomous_research": "自主学习",
    "construction.started": "建设启动",
    "construction.autonomous_started": "自主建设",
    "construction.completed": "建筑完工",
    "monetary.policy_applied": "货币政策",
    "document.judged": "文档审判",
    "message.sent": "发送消息",
    "company.founded": "公司成立",
    "company.job_created": "公司岗位",
    "company.output_accepted": "有效产出",
    "company.output_rejected": "产出返工",
    "housing.rented": "租下住所",
    "housing.bought": "买下住所",
    "housing.bought_for_rent": "买房出租",
    "housing.rent_paid": "支付月租",
    "housing.rested_home": "居家休息",
    "housing.evicted": "住房退租",
    "housing.no_rest_without_home": "无房难休息",
    "identity.text_drifted": "身份文本演化",
  };
  const title = kindNames[event.kind] || zhKind(event.kind);
  const detail = [
    payload.skill,
    payload.query,
    payload.venue,
    payload.name,
    payload.topic,
    payload.action,
    payload.status,
    payload.task_id ? `任务 #${payload.task_id}` : "",
    payload.cost ? `花费 ${payload.cost} agent-credits` : "",
    payload.reward ? `奖励 ${payload.reward} agent-credits` : "",
  ].filter(Boolean).join(" - ");
  return [activityItem(event, "事件", actor, title, detail, [actor, payload.owner].filter(Boolean))];
}

function tickToActivities(event, payload) {
  const items = [];
  const base = { ...event, created_at: event.created_at };
  const push = (suffix, type, actor, title, detail, agentIds = []) => {
    items.push(activityItem({ ...base, id: `${event.id}-${suffix}` }, type, actor, title, detail, agentIds));
  };
  for (const row of payload.completed || []) {
    push(`completed-${row.agent}-${row.task}`, "工作", row.agent, "完成任务并结算收入", `任务 #${row.task}`, [row.agent]);
  }
  for (const row of payload.assigned || []) {
    push(`assigned-${row.agent}-${row.task}`, "工作", row.agent, "领取新任务", `任务 #${row.task}`, [row.agent]);
  }
  for (const row of payload.visits || []) {
    push(`visit-${row.agent}-${row.venue}`, "生活", row.agent, "前往场所恢复状态", `场所：${row.venue}`, [row.agent]);
  }
  for (const row of payload.learned || []) {
    push(`learned-${row.agent}-${row.skill}`, "学习", row.agent, "自主学习新技能", `技能：${row.skill}`, [row.agent]);
  }
  for (const row of payload.trained || []) {
    push(`trained-${row.agent}-${row.training}`, "训练", row.agent, "完成训练", `训练 #${row.training}`, [row.agent]);
  }
  for (const row of payload.social || []) {
    push(`social-${row.agent}-${row.peer || row.with || row.target || row.message || "peer"}`, "社交", row.agent, "与其他智能体交流", compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.anger || []) {
    push(`anger-${row.agent}-${row.reason || row.target || "anger"}`, "情绪", row.agent, "出现愤怒或压力波动", compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.evolved || []) {
    push(`evolved-${row.agent}-${row.algorithm}`, "进化", row.agent, "完成自我进化", `算法：${row.algorithm}`, [row.agent]);
  }
  for (const row of payload.autonomousConstruction || []) {
    push(`auto-build-${row.agent || row.builder}-${row.project_id || row.name}`, "建设", row.agent || row.builder, "自主投资建设", compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.construction || []) {
    const title = row.building_id ? "建筑完工并产生资产" : "建设项目推进";
    push(`build-${row.project_id || row.id}-${row.building_id || row.progress || "progress"}`, "建设", row.builder || row.agent, title, compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.financeResearch || []) {
    push(`finance-${row.agent}-${row.report_id || row.topic}`, "金融", row.agent, "产出金融研究报告", compactDetail(row), [row.agent]);
  }
  for (const row of payload.monetaryPolicy || []) {
    const detail = `动作：${row.action || "hold"} - 流通 ${row.circulating_credits || "?"}/${row.money_supply_cap || "?"}`;
    push(`policy-${row.snapshot_id || row.tick_no || event.id}`, "央行", "credit-bank", "执行货币政策", detail, ["credit-bank"]);
  }
  for (const row of payload.company || []) {
    push(`company-${row.action}-${row.job || row.company || event.id}`, "公司", row.agent || "skillforge-company", companyActionTitle(row.action), compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.housing || []) {
    push(`housing-${row.agent || "world"}-${row.action}-${row.residence || event.id}`, "住房", row.agent || "civic-government", housingActionTitle(row.action), compactDetail(row), compactAgentIds(row));
  }
  for (const row of payload.identity || []) {
    push(`identity-${row.agent}-${row.version}`, "身份", row.agent, "个人文本模型更新", compactDetail(row), [row.agent]);
  }
  return items;
}

function activityItem(event, type, actor, title, detail, agentIds) {
  return {
    key: `event:${event.id}:${type}:${title}`,
    id: event.id,
    type,
    actor: actor || "world",
    title,
    detail: detail || "",
    time: event.created_at || new Date().toISOString(),
    agentIds: [...new Set((agentIds || []).filter(Boolean))],
  };
}

function compactDetail(row) {
  return Object.entries(row || {})
    .filter(([key, value]) => value !== null && value !== undefined && !["agent", "builder", "owner"].includes(key))
    .slice(0, 4)
    .map(([key, value]) => `${zhKey(key)}：${value}`)
    .join(" - ");
}

function compactAgentIds(row) {
  return [...new Set([row.agent, row.builder, row.owner, row.peer, row.with, row.target].filter(Boolean))];
}

function isAgentHot(agentId) {
  const until = state.highlightAgents.get(agentId);
  if (!until) return false;
  if (Date.now() > until) {
    state.highlightAgents.delete(agentId);
    return false;
  }
  return true;
}

function sortActivities(left, right) {
  const bySeen = Number(right.seenAt || 0) - Number(left.seenAt || 0);
  if (bySeen) return bySeen;
  return new Date(right.time).getTime() - new Date(left.time).getTime();
}

function maxId(rows) {
  return rows.reduce((max, row) => Math.max(max, Number(row.id || 0)), 0);
}

function parsePayload(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

function fitCanvas() {
  const rect = canvas.getBoundingClientRect();
  const scale = window.devicePixelRatio || 1;
  canvas.width = Math.max(640, Math.floor(rect.width * scale));
  canvas.height = Math.max(420, Math.floor(rect.height * scale));
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
}

function render() {
  if (!state.world) return;
  fitCanvas();
  renderSummary();
  renderRefreshStatus();
  renderWorld();
  renderControls();
  renderActivityFeed();
  renderAgents();
  renderTasks();
  renderMessages();
  renderQueue();
  renderResearch();
  renderDetail();
  renderEvolution();
  renderRelationships();
  renderLineage();
  renderInstitutions();
  renderMarket();
  renderAssets();
  renderCompany();
  renderHousing();
  renderFinance();
}

function renderSummary() {
  const agents = state.world.agents;
  const active = state.world.tasks.filter((task) => ["open", "in_progress"].includes(task.status)).length;
  const credits = agents.reduce((sum, agent) => sum + agent.credits, 0);
  const queue = state.world.publicationQueue.filter((item) => item.status === "queued").length;
  const mode = state.world.governance ? state.world.governance.topAgentMode : "bootstrap";
  const evolved = state.world.evolutionRuns ? state.world.evolutionRuns.length : 0;
  const buildings = (state.world.buildings || []).length;
  const products = (state.world.products || []).length;
  const companies = (state.world.companies || []).filter((item) => item.status === "active").length;
  const homes = (state.world.residences || []).filter((item) => item.occupant_agent_id).length;
  const listings = (state.world.marketListings || []).filter((item) => item.status === "active").length;
  const globalNoise = (state.world.randomFactors || []).find((item) => item.key === "world.global");
  const noiseText = globalNoise ? ` - OU 随机因子 ${(Number(globalNoise.value) * 100).toFixed(2)}%` : "";
  const policy = (state.world.monetaryPolicy || [])[0];
  const policyText = policy ? ` - 流通 ${policy.circulating_credits}/${policy.money_supply_cap} - 通胀 ${(Number(policy.inflation_rate) * 100).toFixed(2)}%` : "";
  summary.textContent = `${agents.length} 个智能体 - ${credits} agent-credits - ${active} 个活跃任务 - ${queue} 篇待发布 - 公司 ${companies} 家 - 住房 ${homes} 套 - 市场 ${listings} 个挂牌 - 建筑 ${buildings} 个 - 产品 ${products} 个 - 顶层智能体 ${zhStatus(mode)} - 进化事件 ${evolved}${policyText}${noiseText}`;
}

function renderRefreshStatus() {
  if (!refreshStatus) return;
  const last = state.lastRefreshAt
    ? state.lastRefreshAt.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : "等待首次同步";
  const eventId = state.lastSeenEventId ? ` - 最新事件 #${state.lastSeenEventId}` : "";
  refreshStatus.innerHTML = `<span class="live-dot"></span>${state.refreshing ? "正在同步" : "自动刷新"} - ${last}${eventId}`;
}

function renderActivityFeed() {
  const el = document.getElementById("activityFeed");
  if (!el) return;
  const now = Date.now();
  const items = state.activityItems.slice(0, 24);
  if (!items.length) {
    el.innerHTML = `<div class="item"><strong>等待世界产生新动态</strong><span>下一轮同步后会显示工作、学习、消费、建设和金融事件。</span></div>`;
    return;
  }
  el.innerHTML = items.map((item) => {
    const hot = now - Number(item.seenAt || 0) < 6500;
    return `<div class="item activity-item ${hot ? "live" : ""}">
      <strong><span class="activity-type">${escapeHtml(item.type)}</span>${escapeHtml(item.title)}</strong>
      <span>${escapeHtml(formatClock(item.time))} - ${escapeHtml(displayAgent(item.actor))}${item.detail ? ` - ${escapeHtml(item.detail)}` : ""}</span>
    </div>`;
  }).join("");
}

function renderControls() {
  const blueprintSelect = document.getElementById("blueprintSelect");
  const programSelect = document.getElementById("programSelect");
  const nuwaSelect = document.getElementById("nuwaSelect");
  const tradeCategorySelect = document.getElementById("tradeCategorySelect");
  if (blueprintSelect && !blueprintSelect.dataset.ready) {
    blueprintSelect.innerHTML = (state.world.blueprints || [])
      .map((bp) => `<option value="${escapeHtml(bp.id)}">${escapeHtml(zhBlueprintName(bp.id, bp.name))}</option>`)
      .join("");
    blueprintSelect.dataset.ready = "1";
  }
  if (programSelect && !programSelect.dataset.ready) {
    programSelect.innerHTML = (state.world.trainingPrograms || [])
      .map((program) => `<option value="${escapeHtml(program.id)}">${escapeHtml(zhTrainingName(program.id, program.name))}（${program.cost} agent-credits）</option>`)
      .join("");
    programSelect.dataset.ready = "1";
  }
  if (nuwaSelect && !nuwaSelect.dataset.ready) {
    nuwaSelect.innerHTML = (state.world.nuwaDistillations || [])
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(zhNuwaName(item.id, item.display_name))}</option>`)
      .join("");
    nuwaSelect.dataset.ready = "1";
  }
  if (tradeCategorySelect && !tradeCategorySelect.dataset.ready) {
    tradeCategorySelect.innerHTML = (state.world.tradeCategories || [])
      .filter((item) => item.legal_status !== "prohibited")
      .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(zhTradeCategory(item.id, item.name))}（${escapeHtml(zhStatus(item.legal_status))}）</option>`)
      .join("");
    tradeCategorySelect.dataset.ready = "1";
  }
}

function renderWorld() {
  const rect = canvas.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#eef2ec";
  ctx.fillRect(0, 0, w, h);

  drawZone("建造区", 0.08 * w, 0.12 * h, 0.38 * w, 0.33 * h, "#dcebdc");
  drawZone("研究区", 0.54 * w, 0.1 * h, 0.36 * w, 0.33 * h, "#d9edf0");
  drawZone("生活区", 0.14 * w, 0.58 * h, 0.32 * w, 0.28 * h, "#f2e5d4");
  drawZone("审判区", 0.58 * w, 0.58 * h, 0.28 * w, 0.28 * h, "#eee2da");
  drawZone("制度层", 0.41 * w, 0.45 * h, 0.18 * w, 0.12 * h, "#e7e6ef");
  drawZone("市场", 0.04 * w, 0.46 * h, 0.18 * w, 0.1 * h, "#e2eee8");

  for (const home of state.world.residences || []) {
    drawResidence(home, w, h);
  }
  for (const relation of state.world.relationships || []) {
    drawRelationship(relation, w, h);
  }
  const labels = state.world.agents.map((agent) => {
    const point = agentPoint(agent, w, h);
    return { x: point.x - 24, y: point.y - 24, width: 48, height: 48 };
  });
  for (const agent of state.world.agents) {
    drawAgent(agent, w, h);
  }
  for (const agent of state.world.agents) {
    drawAgentLabel(agent, w, h, labels);
  }
}

function drawZone(label, x, y, w, h, fill) {
  ctx.fillStyle = fill;
  ctx.strokeStyle = "#c7d0ce";
  ctx.lineWidth = 1;
  roundedRect(x, y, w, h, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#5f6c71";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(label, x + 12, y + 20);
}

function drawResidence(home, w, h) {
  const x = 32 + Number(home.x || 0.5) * (w - 64);
  const y = 44 + Number(home.y || 0.5) * (h - 88);
  ctx.fillStyle = home.occupant_agent_id ? "#176d5d" : "#ffffff";
  ctx.strokeStyle = "#8aa39d";
  ctx.lineWidth = 1.5;
  roundedRect(x - 10, y - 8, 20, 16, 3);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = home.occupant_agent_id ? "#ffffff" : "#65717a";
  ctx.font = "700 9px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("房", x, y + 3);
}

function drawRelationship(relation, w, h) {
  if (relation.tension < 0.42) return;
  const left = state.world.agents.find((agent) => agent.id === relation.agent_a);
  const right = state.world.agents.find((agent) => agent.id === relation.agent_b);
  if (!left || !right) return;
  const x1 = 32 + left.x * (w - 64);
  const y1 = 44 + left.y * (h - 88);
  const x2 = 32 + right.x * (w - 64);
  const y2 = 44 + right.y * (h - 88);
  ctx.strokeStyle = `rgba(179, 58, 58, ${Math.min(0.8, relation.tension)})`;
  ctx.lineWidth = 1 + relation.tension * 3;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function drawAgent(agent, w, h) {
  const { x, y } = agentPoint(agent, w, h);
  const radius = state.selectedAgent === agent.id ? 23 : 19;
  const color = colors[agent.role] || "#39434a";
  const emotion = agent.emotions || {};
  const alert = emotion.anger > 0.62 || emotion.stress > 0.7;
  const hot = isAgentHot(agent.id);

  if (hot) {
    const remaining = Math.max(0, (state.highlightAgents.get(agent.id) - Date.now()) / 5200);
    ctx.beginPath();
    ctx.arc(x, y, radius + 7 + (1 - remaining) * 5, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(31, 122, 140, ${0.24 + remaining * 0.3})`;
    ctx.lineWidth = 4;
    ctx.stroke();
  }

  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.lineWidth = alert ? 4 : 3;
  ctx.strokeStyle = alert ? "#b33a3a" : "#ffffff";
  ctx.stroke();

  ctx.fillStyle = "#ffffff";
  ctx.font = "700 11px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(agent.id.slice(0, 2).toUpperCase(), x, y + 4);
}

function drawAgentLabel(agent, w, h, labels) {
  const { x, y } = agentPoint(agent, w, h);
  const radius = state.selectedAgent === agent.id ? 23 : 19;
  const emotion = agent.emotions || {};
  const label = emotion.anger > 0.62 ? "愤怒" : zhStatus(agent.state);
  const line1 = agent.name;
  const line2 = `${label} - ${agent.credits} 积分`;
  ctx.font = "12px system-ui, sans-serif";
  const width = Math.ceil(Math.max(ctx.measureText(line1).width, ctx.measureText(line2).width)) + 16;
  const height = 34;
  const candidates = [
    { x: x + radius + 8, y: y - 17 },
    { x: x - width / 2, y: y + radius + 8 },
    { x: x - width - radius - 8, y: y - 17 },
    { x: x - width / 2, y: y - radius - height - 8 },
  ];
  const preferred = candidates.find((box) => labelFits(box, width, height, labels, w, h));
  if (!preferred && state.selectedAgent !== agent.id) return;
  const box = preferred || {
    x: Math.max(8, Math.min(w - width - 8, x + radius + 8)),
    y: Math.max(8, Math.min(h - height - 8, y - 17)),
  };
  labels.push({ x: box.x, y: box.y, width, height });

  ctx.fillStyle = "rgba(255, 255, 255, 0.86)";
  ctx.strokeStyle = "rgba(194, 204, 202, 0.9)";
  ctx.lineWidth = 1;
  roundedRect(box.x, box.y, width, height, 6);
  ctx.fill();
  ctx.stroke();

  ctx.textAlign = "left";
  ctx.fillStyle = "#1e2326";
  ctx.font = "12px system-ui, sans-serif";
  ctx.fillText(line1, box.x + 8, box.y + 14);
  ctx.fillStyle = "#65717a";
  ctx.font = "11px system-ui, sans-serif";
  ctx.fillText(line2, box.x + 8, box.y + 28);
}

function agentPoint(agent, w, h) {
  return {
    x: 32 + agent.x * (w - 64),
    y: 44 + agent.y * (h - 88),
  };
}

function labelFits(box, width, height, labels, w, h) {
  if (box.x < 6 || box.y < 6 || box.x + width > w - 6 || box.y + height > h - 6) return false;
  return labels.every((other) => {
    return (
      box.x + width + 4 < other.x ||
      other.x + other.width + 4 < box.x ||
      box.y + height + 4 < other.y ||
      other.y + other.height + 4 < box.y
    );
  });
}

function roundedRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function renderAgents() {
  const el = document.getElementById("agentList");
  el.innerHTML = state.world.agents.map((agent) => {
    const skills = agent.skills.slice(0, 3).map((skill) => skill.name).join(", ");
    const liveClass = isAgentHot(agent.id) ? " live" : "";
    return `<div class="item agent-card${liveClass}" data-agent="${agent.id}" role="button" tabindex="0">
      <strong>${escapeHtml(agent.name)} <span class="badge">${escapeHtml(zhRole(agent.role))}</span></strong>
      <span>${escapeHtml(zhStatus(agent.state))} - ${agent.credits} agent-credits - 心情 ${agent.mood.toFixed(2)} - 精力 ${agent.energy.toFixed(2)}</span>
      <span>愤怒 ${agent.emotions.anger.toFixed(2)} - 压力 ${agent.emotions.stress.toFixed(2)} - 开心 ${agent.needs.fun.toFixed(2)} - 健康 ${agent.needs.health.toFixed(2)}</span>
      <span>${escapeHtml(skills || "暂无技能")}</span>
    </div>`;
  }).join("");
  for (const item of el.querySelectorAll("[data-agent]")) {
    item.addEventListener("click", () => {
      state.selectedAgent = item.dataset.agent;
      render();
    });
    item.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        state.selectedAgent = item.dataset.agent;
        render();
      }
    });
  }
}

function renderTasks() {
  const el = document.getElementById("taskList");
  el.innerHTML = state.world.tasks.slice(0, 12).map((task) => {
    const cls = task.status === "done" ? "done" : "";
    return `<div class="item">
      <strong><span class="badge ${cls}">${escapeHtml(zhStatus(task.status))}</span>#${task.id} ${escapeHtml(task.title)}</strong>
      <span>${targetLabel(task)} - 报酬 ${task.reward} - 进度 ${Math.round(task.progress)}%</span>
      <div class="bar"><i style="width:${Math.round(task.progress)}%"></i></div>
    </div>`;
  }).join("");
}

function targetLabel(task) {
  if (task.assigned_agent_id) return `智能体 ${task.assigned_agent_id}`;
  if (task.assigned_channel_id) return `群组 ${task.assigned_channel_id}`;
  if (task.assigned_role) return `角色 ${zhRole(task.assigned_role)}`;
  return "未分配";
}

function renderMessages() {
  const el = document.getElementById("messageList");
  el.innerHTML = state.world.messages.slice(0, 12).map((msg) => {
    const target = msg.recipient_id ? `发给 ${msg.recipient_id}` : `在 ${msg.channel_id}`;
    return `<div class="item">
      <strong>${escapeHtml(msg.sender_id)} <span class="meta">${escapeHtml(target)}</span></strong>
      <span>${escapeHtml(msg.body)}</span>
    </div>`;
  }).join("");
}

function renderQueue() {
  const docsById = new Map(state.world.documents.map((doc) => [doc.id, doc]));
  const el = document.getElementById("queueList");
  if (!state.world.publicationQueue.length) {
    el.innerHTML = `<div class="item"><strong>暂无待发布文档</strong><span>通过审判的产物会出现在这里。</span></div>`;
    return;
  }
  el.innerHTML = state.world.publicationQueue.slice(0, 12).map((item) => {
    const doc = docsById.get(item.document_id);
    return `<div class="item">
      <strong><span class="badge queued">${escapeHtml(zhStatus(item.status))}</span>${escapeHtml(item.target)}</strong>
      <span>${escapeHtml(doc ? doc.title : `文档 #${item.document_id}`)}</span>
      <span>外部发布仍需人工确认。</span>
    </div>`;
  }).join("");
}

function renderResearch() {
  const el = document.getElementById("researchList");
  const runs = state.world.researchRuns || [];
  if (!runs.length) {
    el.innerHTML = `<div class="item"><strong>暂无自主研究</strong><span>自驱 agent 空闲时会免费搜索知识并增长技能。</span></div>`;
    return;
  }
  el.innerHTML = runs.slice(0, 12).map((run) => {
    const note = run.note_document_id ? ` - 笔记 #${run.note_document_id}` : "";
    return `<div class="item">
      <strong>${escapeHtml(run.agent_id)} <span class="badge">${escapeHtml(run.skill_name)}</span></strong>
      <span>${escapeHtml(run.query)}${note}</span>
      <span>来源 ${escapeHtml(zhSource(run.source))} - 成本 0 agent-credits</span>
    </div>`;
  }).join("");
}

function renderDetail() {
  const el = document.getElementById("detailPanel");
  const agent = state.world.agents.find((item) => item.id === state.selectedAgent) || state.world.agents[0];
  if (!agent) {
    el.innerHTML = "";
    return;
  }
  state.selectedAgent = agent.id;
  const bars = [
    ["joy", agent.emotions.joy],
    ["anger", agent.emotions.anger],
    ["stress", agent.emotions.stress],
    ["confidence", agent.emotions.confidence],
    ["rest", agent.needs.rest],
    ["social", agent.needs.social],
    ["fun", agent.needs.fun],
    ["purpose", agent.needs.purpose],
    ["health", agent.needs.health],
  ];
  const textProfile = agent.textProfile || {};
  el.innerHTML = `<div class="item">
    <strong>${escapeHtml(agent.name)} <span class="badge">${escapeHtml(zhRole(agent.role))}</span></strong>
    <span>${escapeHtml(zhArchetype(agent.archetype))} - ${agent.credits} agent-credits - 归属 ${escapeHtml(agent.owner_id || "local-owner")}</span>
    <span>贪婪 ${Number(agent.personality.greed || 0.62).toFixed(2)} - 母语 ${escapeHtml(agent.personality.native_language || "zh-CN")}</span>
    <span>身份版本 ${escapeHtml(textProfile.version || 1)} - ${escapeHtml(textProfile.public_identity || "个人文本模型正在形成")}</span>
    <span>当前欲望：${escapeHtml(textProfile.current_desire || "-")}</span>
    <span>情绪叙事：${escapeHtml(textProfile.emotional_tone || "-")}</span>
    <span>恐惧：${escapeHtml(textProfile.fear || "-")}</span>
    ${bars.map(([name, value]) => `<span>${zhMetric(name)} ${Number(value).toFixed(2)}</span><div class="bar"><i style="width:${Math.round(Number(value) * 100)}%"></i></div>`).join("")}
  </div>`;
}

function renderEvolution() {
  const el = document.getElementById("evolutionList");
  const sessions = state.world.trainingSessions || [];
  const runs = state.world.evolutionRuns || [];
  const trainingHtml = sessions.slice(0, 5).map((session) => `<div class="item">
    <strong>训练 #${session.id} <span class="badge">${escapeHtml(zhStatus(session.status))}</span></strong>
    <span>${escapeHtml(session.agent_id)} - ${escapeHtml(session.program_id)} - ${Math.round(session.progress)}%</span>
    <div class="bar"><i style="width:${Math.round(session.progress)}%"></i></div>
  </div>`).join("");
  const runHtml = runs.slice(0, 6).map((run) => `<div class="item">
    <strong>${escapeHtml(run.agent_id)} <span class="badge">${escapeHtml(run.algorithm)}</span></strong>
    <span>${run.accepted ? "接受" : "拒绝"} - 适应度 ${Number(run.old_fitness).toFixed(2)} -> ${Number(run.new_fitness).toFixed(2)}</span>
    <span>温度 ${Number(run.temperature).toFixed(2)} - 变异 ${Number(run.mutation_rate).toFixed(2)}</span>
  </div>`).join("");
  el.innerHTML = trainingHtml + runHtml || `<div class="item"><strong>暂无训练</strong><span>开始训练或推进世界时间。</span></div>`;
}

function renderRelationships() {
  const el = document.getElementById("relationshipList");
  const rows = state.world.relationships || [];
  el.innerHTML = rows.slice(0, 12).map((row) => `<div class="item">
    <strong>${escapeHtml(row.agent_a)} - ${escapeHtml(row.agent_b)} <span class="badge">${escapeHtml(zhEvent(row.last_event))}</span></strong>
    <span>亲近 ${Number(row.affinity).toFixed(2)} - 信任 ${Number(row.trust).toFixed(2)} - 紧张 ${Number(row.tension).toFixed(2)}</span>
  </div>`).join("") || `<div class="item"><strong>暂无关系记录</strong></div>`;
}

function renderLineage() {
  const el = document.getElementById("lineageList");
  const rows = state.world.lineage || [];
  el.innerHTML = rows.slice(0, 12).map((row) => `<div class="item">
    <strong>${escapeHtml(row.child_agent_id)} <span class="badge">${escapeHtml(row.method)}</span></strong>
    <span>父代 ${escapeHtml(row.parent_ids_json)} - 变异率 ${Number(row.mutation_rate).toFixed(2)} - 成本 ${row.cost}</span>
  </div>`).join("") || `<div class="item"><strong>暂无子代 agent</strong><span>使用繁衍谱系孵化新 agent。</span></div>`;
}

function renderInstitutions() {
  const el = document.getElementById("institutionList");
  const rows = state.world.institutions || [];
  el.innerHTML = rows.map((item) => `<div class="item">
    <strong>${escapeHtml(zhInstitutionName(item.id, item.name))} <span class="badge">${escapeHtml(zhRole(item.kind))}</span></strong>
    <span>控制智能体 ${escapeHtml(item.controlled_agent_id || "-")} - 预算 ${item.budget_credits} - 权限 ${item.authority_level}</span>
    <span>${escapeHtml(zhInstitutionMandate(item.id, item.mandate))}</span>
  </div>`).join("") || `<div class="item"><strong>暂无制度层</strong></div>`;
}

function renderMarket() {
  const el = document.getElementById("marketList");
  const listings = state.world.marketListings || [];
  const transactions = state.world.marketTransactions || [];
  const listingHtml = listings.slice(0, 8).map((item) => `<div class="item">
    <strong>#${item.id} ${escapeHtml(item.item_name)} <span class="badge ${item.status === "sold" ? "done" : ""}">${escapeHtml(zhStatus(item.status))}</span></strong>
    <span>${escapeHtml(zhTradeCategory(item.item_type, item.item_type))} - 卖家 ${escapeHtml(item.seller_agent_id)} - 价格 ${item.price} agent-credits</span>
    <span>合法性 ${escapeHtml(zhStatus(item.legality_status))} - 审核 ${escapeHtml(item.reviewed_by || "-")}</span>
  </div>`).join("");
  const transactionHtml = transactions.slice(0, 4).map((item) => `<div class="item">
    <strong>交易 #${item.id} <span class="badge done">${item.price} agent-credits</span></strong>
    <span>${escapeHtml(item.buyer_agent_id)} 向 ${escapeHtml(item.seller_agent_id)} 购买 - ${escapeHtml(item.legal_basis)}</span>
  </div>`).join("");
  el.innerHTML = listingHtml + transactionHtml || `<div class="item"><strong>暂无市场活动</strong></div>`;
}

function renderAssets() {
  const el = document.getElementById("assetList");
  const buildings = state.world.buildings || [];
  const projects = state.world.constructionProjects || [];
  const products = state.world.products || [];
  const projectHtml = projects.slice(0, 5).map((item) => `<div class="item">
    <strong>建设项目 #${item.id} <span class="badge">${escapeHtml(zhStatus(item.status))}</span></strong>
    <span>${escapeHtml(item.name)} - 建设者 ${escapeHtml(item.builder_agent_id)} - 所有者 ${escapeHtml(item.owner_agent_id)}</span>
    <div class="bar"><i style="width:${Math.round(item.progress)}%"></i></div>
  </div>`).join("");
  const buildingHtml = buildings.slice(0, 5).map((item) => `<div class="item">
    <strong>建筑 #${item.id} ${escapeHtml(item.name)}</strong>
    <span>所有者 ${escapeHtml(item.owner_agent_id)} - 价值 ${item.value} - 租金 ${item.rent_per_tick}</span>
  </div>`).join("");
  const productHtml = products.slice(0, 6).map((item) => `<div class="item">
    <strong>产品 #${item.id} ${escapeHtml(item.name)} <span class="badge">${escapeHtml(zhStatus(item.status))}</span></strong>
    <span>设计者 ${escapeHtml(item.designer_agent_id)} - 价格 ${item.unit_price} - 库存 ${item.stock} - 质量 ${Number(item.quality).toFixed(2)}</span>
  </div>`).join("");
  el.innerHTML = projectHtml + buildingHtml + productHtml || `<div class="item"><strong>暂无资产</strong></div>`;
}

function renderCompany() {
  const el = document.getElementById("companyList");
  if (!el) return;
  const companies = state.world.companies || [];
  const jobs = state.world.companyJobs || [];
  const outputs = state.world.companyOutputs || [];
  const needs = state.world.materialNeeds || [];
  const companyHtml = companies.slice(0, 3).map((item) => `<div class="item policy-item">
    <strong>${escapeHtml(item.name)} <span class="badge">${escapeHtml(zhStatus(item.status))}</span></strong>
    <span>资金 ${item.treasury_credits} agent-credits - 需求 ${Number(item.demand_score).toFixed(2)}</span>
    <span>${escapeHtml(item.mission)}</span>
  </div>`).join("") || `<div class="item"><strong>公司尚未成立</strong><span>世界稳定后会自动成立 SkillForge 开源技能公司。</span></div>`;
  const jobHtml = jobs.slice(0, 5).map((job) => `<div class="item">
    <strong>岗位 #${job.id} <span class="badge">${escapeHtml(zhStatus(job.status))}</span></strong>
    <span>${escapeHtml(job.industry)} - ${escapeHtml(zhTradeCategory(job.output_type, job.output_type))} - 报酬 ${job.reward}</span>
    <span>${escapeHtml(job.title)} - 任务 #${job.task_id || "-"}</span>
  </div>`).join("");
  const outputHtml = outputs.slice(0, 4).map((item) => `<div class="item">
    <strong>有效产出 #${item.id} <span class="badge done">${Number(item.effectiveness_score).toFixed(2)}</span></strong>
    <span>${escapeHtml(item.agent_id)} - ${escapeHtml(item.industry)} - 奖励 ${item.reward}</span>
    <span>${escapeHtml(item.title)}</span>
  </div>`).join("");
  const needHtml = needs.slice(0, 3).map((item) => `<div class="item">
    <strong>资料需求 #${item.id} <span class="badge queued">${Number(item.demand_score).toFixed(2)}</span></strong>
    <span>${escapeHtml(item.industry)} - ${escapeHtml(item.topic)}</span>
  </div>`).join("");
  el.innerHTML = companyHtml + jobHtml + outputHtml + needHtml;
}

function renderHousing() {
  const el = document.getElementById("housingList");
  if (!el) return;
  const rows = state.world.residences || [];
  el.innerHTML = rows.slice(0, 12).map((home) => `<div class="item">
    <strong>住所 #${home.id} ${escapeHtml(home.name)} <span class="badge">${escapeHtml(zhStatus(home.status))}</span></strong>
    <span>居住 ${escapeHtml(home.occupant_agent_id || "-")} - 所有者 ${escapeHtml(home.owner_agent_id || "-")}</span>
    <span>买价 ${home.purchase_price} - 月租 ${home.monthly_rent} - 舒适 ${Number(home.comfort).toFixed(2)}${home.status === "for_rent" && home.owner_agent_id ? " - 可被其他 agent 租住" : ""}</span>
  </div>`).join("") || `<div class="item"><strong>暂无住房</strong></div>`;
}

function renderFinance() {
  const el = document.getElementById("financeList");
  const rows = state.world.financialResearchReports || [];
  const policy = (state.world.monetaryPolicy || [])[0];
  const policyHtml = policy ? `<div class="item policy-item">
    <strong>央行货币政策 <span class="badge">${escapeHtml(policy.action)}</span></strong>
    <span>流通 credits：${policy.circulating_credits} / 上限 ${policy.money_supply_cap} - 银行储备：${policy.bank_reserves} / 上限 ${policy.bank_reserve_cap}</span>
    <span>价格指数 ${Number(policy.price_index).toFixed(3)} - 通胀 ${(Number(policy.inflation_rate) * 100).toFixed(2)}% - 政策利率 ${(Number(policy.policy_rate) * 100).toFixed(2)}%</span>
  </div>` : `<div class="item"><strong>暂无货币政策快照</strong><span>推进一轮世界后，credit-bank 会用 MV=PY 代理模型计算供给上限。</span></div>`;
  const reportHtml = rows.slice(0, 10).map((item) => `<div class="item">
    <strong>报告 #${item.id} <span class="badge">${Number(item.usefulness_score).toFixed(2)}</span></strong>
    <span>${escapeHtml(item.researcher_agent_id)} - ${escapeHtml(item.model_name)}</span>
    <span>${escapeHtml(item.topic)}</span>
    <span>${escapeHtml(item.path)}</span>
  </div>`).join("") || `<div class="item"><strong>暂无金融报告</strong><span>让研究员汇总小世界经济模型。</span></div>`;
  el.innerHTML = policyHtml + reportHtml;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function zhRole(value) {
  return roleNames[value] || value;
}

function zhStatus(value) {
  return statusNames[value] || value;
}

function zhArchetype(value) {
  return archetypeNames[value] || value;
}

function zhEvent(value) {
  return eventNames[value] || value;
}

function zhTradeCategory(id, fallback) {
  return tradeCategoryNames[id] || fallback || id;
}

function zhInstitutionName(id, fallback) {
  return institutionNames[id] || fallback || id;
}

function zhInstitutionMandate(id, fallback) {
  return institutionMandates[id] || fallback || "";
}

function zhSource(value) {
  return sourceNames[value] || value;
}

function zhMetric(value) {
  return metricNames[value] || value;
}

function zhKind(value) {
  const names = {
    "task.assigned": "任务分配",
    "task.completed": "任务完成",
    "venue.visited": "生活消费",
    "skill.autonomous_research": "自主研究",
    "construction.started": "建设启动",
    "construction.autonomous_started": "自主建设",
    "construction.completed": "建筑完工",
    "monetary.policy_applied": "货币政策",
    "company.founded": "公司成立",
    "company.job_created": "公司岗位",
    "company.output_accepted": "有效产出",
    "company.output_rejected": "产出返工",
    "housing.rented": "租房",
    "housing.bought": "买房",
    "housing.rested_home": "居家休息",
    "housing.evicted": "住房退租",
    "housing.no_rest_without_home": "无房难休息",
    "world.tick": "世界推进",
  };
  return names[value] || value;
}

function companyActionTitle(action) {
  return {
    founded: "公司成立并开始招工",
    job_created: "公司发布付费岗位",
  }[action] || "公司发生变化";
}

function housingActionTitle(action) {
  return {
    rented: "租下住所",
    bought: "买下住所",
    bought_for_rent: "买下资产并挂牌出租",
    rested_home: "在家休息恢复",
    rent_paid: "支付月租",
    evicted: "因欠租退租",
    no_home_cannot_rest: "没有住房无法休息",
  }[action] || "住房状态变化";
}

function zhKey(value) {
  const names = {
    agent: "智能体",
    builder: "建设者",
    owner: "所有者",
    peer: "伙伴",
    with: "对象",
    target: "对象",
    skill: "技能",
    venue: "场所",
    project_id: "项目",
    building_id: "建筑",
    report_id: "报告",
    topic: "主题",
    progress: "进度",
    cost: "成本",
    value: "价值",
    random_factor: "随机因子",
    algorithm: "算法",
    action: "动作",
    company: "公司",
    job: "岗位",
    task: "任务",
    industry: "行业",
    output_type: "产出类型",
    residence: "住所",
    amount: "金额",
    version: "版本",
    desire: "欲望",
    fear: "恐惧",
    rent: "租金",
    monthly_rent: "月租",
  };
  return names[value] || value;
}

function displayAgent(agentId) {
  const agent = state.world && (state.world.agents || []).find((item) => item.id === agentId);
  return agent ? `${agent.name}（${agent.id}）` : agentId;
}

function formatClock(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "刚刚";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function zhTrainingName(id, fallback) {
  const names = {
    "deep-research-lab": "深度研究实验室",
    "builder-bootcamp": "建造者训练营",
    "storycraft-studio": "叙事写作工作室",
    "social-dynamics-dojo": "社交协作道场",
    "emotional-regulation-bar": "情绪调节酒吧",
  };
  return names[id] || fallback;
}

function zhBlueprintName(id, fallback) {
  const names = {
    researcher: "研究侦察员",
    engineer: "实践建造者",
    documentarian: "知识写作者",
    social: "社区主持人",
  };
  return names[id] || fallback;
}

function zhNuwaName(id, fallback) {
  const names = {
    "steve-jobs": "乔布斯视角",
    "richard-feynman": "费曼视角",
    "charlie-munger": "芒格视角",
    "andrej-karpathy": "Karpathy 视角",
  };
  return names[id] || fallback;
}

document.getElementById("tickBtn").addEventListener("click", async () => {
  try {
    await api("/api/tick", { method: "POST", body: JSON.stringify({ steps: 1 }) });
    showToast("小世界已推进一轮");
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("ralphBtn").addEventListener("click", async () => {
  try {
    const result = await api("/api/ralph-plan", { method: "POST", body: "{}" });
    showToast(`已写入 ${result.path}`);
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("summaryBtn").addEventListener("click", async () => {
  try {
    const result = await api("/api/summary/export", { method: "POST", body: "{}" });
    showToast(`已导出世界汇总：${result.path}`);
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: data.title,
        description: data.description,
        reward: Number(data.reward),
        [data.targetType]: data.target,
      }),
    });
    event.currentTarget.reset();
    event.currentTarget.elements.reward.value = 80;
    event.currentTarget.elements.target.value = "makers";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("messageForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/messages", {
      method: "POST",
      body: JSON.stringify({ sender: data.sender, body: data.body, [data.targetType]: data.target }),
    });
    event.currentTarget.elements.body.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("agentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/agents", {
      method: "POST",
      body: JSON.stringify({ name: data.name, blueprint: data.blueprint, owner: data.owner, credits: Number(data.credits) }),
    });
    event.currentTarget.elements.name.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("trainingForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/training", { method: "POST", body: JSON.stringify({ agent: data.agent, program: data.program }) });
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("lineageForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/reproduce", {
      method: "POST",
      body: JSON.stringify({ name: data.name, parents: data.parents, mutationRate: Number(data.mutationRate) }),
    });
    event.currentTarget.elements.name.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("nuwaForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/nuwa-agents", {
      method: "POST",
      body: JSON.stringify({ figure: data.figure, name: data.name || undefined }),
    });
    event.currentTarget.elements.name.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("marketForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/market-listings", {
      method: "POST",
      body: JSON.stringify({ seller: data.seller, itemType: data.itemType, name: data.name, description: data.description, price: Number(data.price) }),
    });
    event.currentTarget.elements.name.value = "";
    event.currentTarget.elements.description.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("marketBuyForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/market-buy", {
      method: "POST",
      body: JSON.stringify({ buyer: data.buyer, listing: Number(data.listing) }),
    });
    event.currentTarget.elements.listing.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("constructionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/construction", {
      method: "POST",
      body: JSON.stringify({ builder: data.builder, name: data.name, kind: data.kind, cost: Number(data.cost) }),
    });
    event.currentTarget.elements.name.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("productForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/products", {
      method: "POST",
      body: JSON.stringify({ designer: data.designer, name: data.name, category: "tool", price: Number(data.price), buildCost: 0, stock: Number(data.stock) }),
    });
    event.currentTarget.elements.name.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("financeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/finance-research", {
      method: "POST",
      body: JSON.stringify({ agent: data.agent, topic: data.topic }),
    });
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("housingRentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/housing-rent", {
      method: "POST",
      body: JSON.stringify({ agent: data.agent, residence: Number(data.residence) }),
    });
    event.currentTarget.elements.residence.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("housingBuyForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/housing-buy", {
      method: "POST",
      body: JSON.stringify({ agent: data.agent, residence: Number(data.residence) }),
    });
    event.currentTarget.elements.residence.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("housingInvestForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.currentTarget).entries());
  try {
    await api("/api/housing-invest", {
      method: "POST",
      body: JSON.stringify({ agent: data.agent, residence: Number(data.residence), rent: data.rent ? Number(data.rent) : null }),
    });
    event.currentTarget.elements.residence.value = "";
    event.currentTarget.elements.rent.value = "";
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

document.getElementById("recordBtn").addEventListener("click", async () => {
  try {
    const result = await api("/api/records/export", { method: "POST", body: "{}" });
    showToast(`已导出 ${result.count} 个记录文件`);
    await refresh();
  } catch (err) {
    showToast(err.message);
  }
});

canvas.addEventListener("click", (event) => {
  if (!state.world) return;
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  let best = null;
  let bestDist = Infinity;
  for (const agent of state.world.agents) {
    const ax = 32 + agent.x * (rect.width - 64);
    const ay = 44 + agent.y * (rect.height - 88);
    const dist = Math.hypot(x - ax, y - ay);
    if (dist < bestDist) {
      best = agent;
      bestDist = dist;
    }
  }
  if (best && bestDist < 36) {
    state.selectedAgent = best.id;
    render();
  }
});

window.addEventListener("resize", render);
refresh().catch((err) => showToast(err.message));
window.setInterval(() => refresh({ silent: true }).catch(() => {}), 2500);
