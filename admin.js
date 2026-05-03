const store = window.GazelStore;

const loginView = document.querySelector("#loginView");
const authShell = document.querySelector("#adminAuthShell");
const dashboard = document.querySelector("#adminDashboard");

const loginForm = document.querySelector("#loginForm");
const createAccountForm = document.querySelector("#createAccountForm");
const changePasswordForm = document.querySelector("#changePasswordForm");
const logoutButton = document.querySelector("#logoutButton");
const exportExcelButton = document.querySelector("#exportExcelButton");
const resetOrdersFilterButton = document.querySelector("#resetOrdersFilterButton");

const loginMessage = document.querySelector("#loginMessage");
const createAccountMessage = document.querySelector("#createAccountMessage");
const passwordMessage = document.querySelector("#passwordMessage");
const accountsMessage = document.querySelector("#accountsMessage");
const ordersMessage = document.querySelector("#ordersMessage");

const sessionInfo = document.querySelector("#sessionInfo");
const totalOrders = document.querySelector("#totalOrders");
const todayOrders = document.querySelector("#todayOrders");
const accountsCount = document.querySelector("#accountsCount");
const ordersCountBadge = document.querySelector("#ordersCountBadge");
const archivedOrdersCountBadge = document.querySelector("#archivedOrdersCountBadge");
const ordersList = document.querySelector("#ordersList");
const archivedOrdersList = document.querySelector("#archivedOrdersList");
const accountsList = document.querySelector("#accountsList");
const passwordAccount = document.querySelector("#passwordAccount");
const ordersDateFrom = document.querySelector("#ordersDateFrom");
const ordersDateTo = document.querySelector("#ordersDateTo");

const ORDER_STATUS_META = {
  new: {
    label: "Новая",
    pillClass: "admin-count-pill-accent",
  },
  in_progress: {
    label: "В процессе",
    pillClass: "admin-count-pill-progress",
  },
  completed: {
    label: "Выполнено",
    pillClass: "admin-count-pill-success",
  },
};

const dashboardState = {
  activeAccount: null,
  accounts: [],
  orders: [],
};

const createElement = (tagName, className, text) => {
  const element = document.createElement(tagName);

  if (className) {
    element.className = className;
  }

  if (text !== undefined) {
    element.textContent = text;
  }

  return element;
};

const formatDate = (value, options) => {
  if (!value) {
    return "Не указано";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Не указано";
  }

  return date.toLocaleString("ru-RU", options);
};

const getLocalDateKey = (value) => {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const year = String(date.getFullYear());
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
};

const formatOrdersCount = (value) => {
  if (value % 10 === 1 && value % 100 !== 11) {
    return `${value} заявка`;
  }

  if ([2, 3, 4].includes(value % 10) && ![12, 13, 14].includes(value % 100)) {
    return `${value} заявки`;
  }

  return `${value} заявок`;
};

const normalizeOrderStatus = (value) => {
  if (value === "in_progress") {
    return "in_progress";
  }

  if (value === "completed") {
    return "completed";
  }

  return "new";
};

const getOrderStatusMeta = (value) => ORDER_STATUS_META[normalizeOrderStatus(value)] || ORDER_STATUS_META.new;

const setFeedback = (node, message, type = "success") => {
  if (!node) {
    return;
  }

  if (!message) {
    node.hidden = true;
    node.textContent = "";
    node.className = "admin-feedback";
    return;
  }

  node.hidden = false;
  node.textContent = message;
  node.className = `admin-feedback ${type}`;
};

const clearDashboardFeedback = () => {
  setFeedback(createAccountMessage, "");
  setFeedback(passwordMessage, "");
  setFeedback(accountsMessage, "");
  setFeedback(ordersMessage, "");
};

const showLoginView = () => {
  authShell.hidden = false;
  dashboard.hidden = true;
  loginView.hidden = false;
};

const showDashboard = () => {
  authShell.hidden = true;
  dashboard.hidden = false;
};

const createOrderField = (label, value, full = false) => {
  const field = createElement("div", `admin-order-field${full ? " full" : ""}`);
  const caption = createElement("span", "", label);
  const content = createElement("strong", "", value || "Не указано");

  field.append(caption, content);
  return field;
};

const getOrdersDateRange = () => {
  let from = ordersDateFrom?.value || "";
  let to = ordersDateTo?.value || "";

  if (from && to && from > to) {
    [from, to] = [to, from];
  }

  return { from, to };
};

const hasOrdersDateFilter = () => {
  const { from, to } = getOrdersDateRange();
  return Boolean(from || to);
};

const filterOrdersByDate = (orders) => {
  const { from, to } = getOrdersDateRange();

  if (!from && !to) {
    return orders;
  }

  return orders.filter((order) => {
    const createdAtKey = getLocalDateKey(order.createdAt);

    if (!createdAtKey) {
      return false;
    }

    if (from && createdAtKey < from) {
      return false;
    }

    if (to && createdAtKey > to) {
      return false;
    }

    return true;
  });
};

const getEmptyOrdersMessage = (type, totalOrders) => {
  if (!totalOrders) {
    if (type === "active") {
      return "Пока нет ни одной заявки. После отправки формы на главной странице они появятся здесь автоматически.";
    }

    return "В архиве пока нет ни одной выполненной заявки.";
  }

  if (hasOrdersDateFilter()) {
    if (type === "active") {
      return "По выбранной дате активных заявок не найдено.";
    }

    return "По выбранной дате в архиве ничего не найдено.";
  }

  if (type === "active") {
    return "Активных заявок сейчас нет. Выполненные заявки перенесены в архив.";
  }

  return "В архиве пока нет ни одной выполненной заявки.";
};

const createOrderStatusControl = (order) => {
  const currentStatus = normalizeOrderStatus(order.status);
  const wrapper = createElement("label", "admin-order-status");
  const caption = createElement("span", "", "Статус");
  const select = createElement("select");

  Object.entries(ORDER_STATUS_META).forEach(([value, meta]) => {
    const option = createElement("option", "", meta.label);
    option.value = value;
    select.append(option);
  });

  select.value = currentStatus;

  select.addEventListener("change", async () => {
    const nextStatus = select.value;

    if (nextStatus === currentStatus) {
      return;
    }

    setFeedback(ordersMessage, "");
    select.disabled = true;

    try {
      await store.updateOrderStatus(order.id, nextStatus);
      await renderDashboard();

      if (nextStatus === "completed") {
        setFeedback(ordersMessage, "Заявка отмечена как выполненная и перенесена в архив.", "success");
        return;
      }

      const nextStatusMeta = getOrderStatusMeta(nextStatus);

      if (currentStatus === "completed") {
        setFeedback(
          ordersMessage,
          `Заявка возвращена из архива со статусом «${nextStatusMeta.label}».`,
          "success"
        );
        return;
      }

      setFeedback(ordersMessage, `Статус заявки изменён на «${nextStatusMeta.label}».`, "success");
    } catch (error) {
      select.value = currentStatus;
      select.disabled = false;
      setFeedback(ordersMessage, error.message, "error");
    }
  });

  wrapper.append(caption, select);
  return wrapper;
};

const createOrderCard = (order, index, total) => {
  const statusMeta = getOrderStatusMeta(order.status);
  const isArchived = normalizeOrderStatus(order.status) === "completed";
  const card = createElement("article", `admin-order-card${isArchived ? " archived" : ""}`);
  const top = createElement("div", "admin-order-top");
  const headline = createElement("div", "admin-order-headline");
  const title = createElement("h3", "admin-order-title", order.customer || `Заявка #${total - index}`);
  const meta = createElement(
    "p",
    "admin-order-meta",
    `Получена ${formatDate(order.createdAt, { dateStyle: "medium", timeStyle: "short" })}`
  );
  const pill = createElement("span", `admin-count-pill ${statusMeta.pillClass}`, statusMeta.label);
  const grid = createElement("div", "admin-order-grid");
  const actions = createElement("div", "admin-order-actions");

  headline.append(title, meta);
  top.append(headline, pill);

  grid.append(
    createOrderField("Контакты заказчика", order.customer),
    createOrderField("Телефон", order.phone),
    createOrderField("Тип машины", order.truckType),
    createOrderField(
      "Дата и время подачи",
      formatDate(order.dateTime, { dateStyle: "long", timeStyle: "short" })
    ),
    createOrderField("Описание груза", order.cargo, true)
  );

  actions.append(createOrderStatusControl(order));
  card.append(top, grid, actions);

  return card;
};

const renderOrderList = (node, orders, emptyMessage) => {
  node.replaceChildren();

  if (!orders.length) {
    node.append(createElement("div", "admin-empty", emptyMessage));
    return;
  }

  orders.forEach((order, index) => {
    node.append(createOrderCard(order, index, orders.length));
  });
};

const renderOrders = (orders) => {
  const filteredOrders = filterOrdersByDate(orders);
  const activeOrders = filteredOrders.filter((order) => normalizeOrderStatus(order.status) !== "completed");
  const archivedOrders = filteredOrders.filter((order) => normalizeOrderStatus(order.status) === "completed");

  ordersCountBadge.textContent = formatOrdersCount(activeOrders.length);

  if (archivedOrdersCountBadge) {
    archivedOrdersCountBadge.textContent = formatOrdersCount(archivedOrders.length);
  }

  renderOrderList(ordersList, activeOrders, getEmptyOrdersMessage("active", orders.length));

  if (archivedOrdersList) {
    renderOrderList(archivedOrdersList, archivedOrders, getEmptyOrdersMessage("archived", orders.length));
  }
};

const renderAccounts = (accounts, activeAccount) => {
  accountsList.replaceChildren();
  passwordAccount.replaceChildren();

  accounts.forEach((account) => {
    const option = createElement("option", "", account.displayLogin);
    option.value = account.login;
    passwordAccount.append(option);
  });

  accounts.forEach((account) => {
    const row = createElement("div", "admin-account-row");
    const meta = createElement("div", "admin-account-meta");
    const title = createElement("strong", "", account.displayLogin);
    const created = createElement(
      "span",
      "",
      `Создан ${formatDate(account.createdAt, { dateStyle: "medium", timeStyle: "short" })}`
    );
    const badges = createElement("div", "admin-badges");
    const actions = createElement("div", "admin-row-actions");
    const deleteButton = createElement("button", "admin-row-button admin-row-button-danger", "Удалить");

    deleteButton.type = "button";

    if (account.login === activeAccount.login) {
      badges.append(createElement("span", "admin-inline-badge", "Текущий"));
      deleteButton.disabled = true;
      deleteButton.title = "Нельзя удалить аккаунт, под которым выполнен вход.";
    }

    if (accounts.length <= 1) {
      deleteButton.disabled = true;
      deleteButton.title = "Последний аккаунт удалить нельзя.";
    }

    deleteButton.addEventListener("click", async () => {
      const confirmed = window.confirm(`Удалить аккаунт ${account.displayLogin}?`);

      if (!confirmed) {
        return;
      }

      try {
        await store.deleteAccount(account.login);
        setFeedback(accountsMessage, "Аккаунт удалён.", "success");
        await renderDashboard();
      } catch (error) {
        setFeedback(accountsMessage, error.message, "error");
      }
    });

    meta.append(title, created);
    actions.append(deleteButton);
    row.append(meta, badges, actions);
    accountsList.append(row);
  });
};

const renderStats = (orders, accounts) => {
  const todayKey = new Date().toLocaleDateString("ru-RU");
  const todayCount = orders.filter(
    (order) => formatDate(order.createdAt, { dateStyle: "short" }) === todayKey
  ).length;

  totalOrders.textContent = String(orders.length);
  todayOrders.textContent = String(todayCount);
  accountsCount.textContent = String(accounts.length);
};

const rerenderOrdersByFilter = () => {
  setFeedback(ordersMessage, "");
  renderOrders(dashboardState.orders);
};

const renderDashboard = async () => {
  const activeAccount = await store.getCurrentAdmin();

  if (!activeAccount) {
    const bootstrap = await store.getBootstrap();
    showLoginView();

    if (!bootstrap.hasAdmins) {
      setFeedback(
        loginMessage,
        "В базе пока нет админов. Если аккаунт уже создавался в старой версии сайта, откройте проект через server.py на этом компьютере, и он перенесётся в базу автоматически. Если это новый запуск, создайте первого администратора командой: python3 server.py --create-admin LOGIN PASSWORD",
        "error"
      );
    }

    return;
  }

  clearDashboardFeedback();
  setFeedback(loginMessage, "");

  const [orders, accounts] = await Promise.all([store.getOrders(), store.getAccounts()]);

  dashboardState.activeAccount = activeAccount;
  dashboardState.orders = orders;
  dashboardState.accounts = accounts;

  sessionInfo.textContent = `Вы вошли как ${activeAccount.displayLogin}. Здесь можно фильтровать заявки по дате поступления, менять их статус и отправлять выполненные заявки в архив.`;

  renderStats(orders, accounts);
  renderOrders(orders);
  renderAccounts(accounts, activeAccount);

  if (exportExcelButton) {
    exportExcelButton.href = store.exportOrdersUrl;
  }

  showDashboard();
};

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    setFeedback(loginMessage, "");

    const formData = new FormData(loginForm);

    try {
      await store.verifyLogin(formData.get("login"), formData.get("password"));
      loginForm.reset();
      await renderDashboard();
    } catch (error) {
      setFeedback(loginMessage, error.message, "error");
    }
  });
}

if (createAccountForm) {
  createAccountForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearDashboardFeedback();

    const formData = new FormData(createAccountForm);

    try {
      await store.createAccount(formData.get("login"), formData.get("password"));
      createAccountForm.reset();
      await renderDashboard();
      setFeedback(createAccountMessage, "Новый аккаунт создан.", "success");
    } catch (error) {
      setFeedback(createAccountMessage, error.message, "error");
    }
  });
}

if (changePasswordForm) {
  changePasswordForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearDashboardFeedback();

    const formData = new FormData(changePasswordForm);
    const login = formData.get("login");

    try {
      await store.updatePassword(login, formData.get("password"));
      changePasswordForm.reset();
      await renderDashboard();
      passwordAccount.value = store.normalizeLogin(login);
      setFeedback(passwordMessage, "Пароль обновлён.", "success");
    } catch (error) {
      setFeedback(passwordMessage, error.message, "error");
    }
  });
}

if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    await store.logout();

    if (ordersDateFrom) {
      ordersDateFrom.value = "";
    }

    if (ordersDateTo) {
      ordersDateTo.value = "";
    }

    showLoginView();
  });
}

if (ordersDateFrom) {
  ordersDateFrom.addEventListener("input", rerenderOrdersByFilter);
}

if (ordersDateTo) {
  ordersDateTo.addEventListener("input", rerenderOrdersByFilter);
}

if (resetOrdersFilterButton) {
  resetOrdersFilterButton.addEventListener("click", () => {
    if (ordersDateFrom) {
      ordersDateFrom.value = "";
    }

    if (ordersDateTo) {
      ordersDateTo.value = "";
    }

    rerenderOrdersByFilter();
  });
}

const initializeAdminPanel = async () => {
  try {
    await store.init();
    await renderDashboard();
  } catch (error) {
    showLoginView();
    setFeedback(loginMessage, "Не удалось подключиться к серверу. Запустите server.py.", "error");
  }
};

initializeAdminPanel();
