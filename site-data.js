(() => {
  const LEGACY_ORDERS_KEY = "gazelExpressOrders";
  const LEGACY_ACCOUNTS_KEY = "gazelExpressAdminAccounts";
  let bootstrapCache = null;
  let initPromise = null;

  const safeRead = (key, fallback) => {
    try {
      const raw = localStorage.getItem(key);

      if (!raw) {
        return fallback;
      }

      return JSON.parse(raw);
    } catch (error) {
      return fallback;
    }
  };

  const normalizeLogin = (value) => String(value || "").trim().toLowerCase();
  const trimValue = (value) => String(value || "").trim();

  const request = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});

    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    if (options.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
      headers,
    });

    const contentType = response.headers.get("Content-Type") || "";
    let payload = {};

    if (contentType.includes("application/json")) {
      try {
        payload = await response.json();
      } catch (error) {
        payload = {};
      }
    }

    if (!response.ok) {
      throw new Error(payload.message || "Ошибка сервера.");
    }

    return payload;
  };

  const migrateLegacyData = async (bootstrap) => {
    const legacyAccounts = safeRead(LEGACY_ACCOUNTS_KEY, []);
    const legacyOrders = safeRead(LEGACY_ORDERS_KEY, []);
    const shouldMigrateAccounts = !bootstrap.hasAdmins && legacyAccounts.length > 0;
    const shouldMigrateOrders = Number(bootstrap.orderCount || 0) === 0 && legacyOrders.length > 0;

    if (!shouldMigrateAccounts && !shouldMigrateOrders) {
      return bootstrap;
    }

    await request("/api/migrate-legacy", {
      method: "POST",
      body: JSON.stringify({
        accounts: shouldMigrateAccounts ? legacyAccounts : [],
        orders: shouldMigrateOrders ? legacyOrders : [],
      }),
    });

    return request("/api/bootstrap");
  };

  const init = async () => {
    if (!initPromise) {
      initPromise = (async () => {
        const bootstrap = await request("/api/bootstrap");
        bootstrapCache = await migrateLegacyData(bootstrap);
        return bootstrapCache;
      })().catch((error) => {
        initPromise = null;
        throw error;
      });
    }

    return initPromise;
  };

  const refreshBootstrap = async () => {
    bootstrapCache = await request("/api/bootstrap");
    return bootstrapCache;
  };

  const ensureReady = async () => bootstrapCache || init();

  window.GazelStore = {
    init,
    normalizeLogin,
    exportOrdersUrl: "/api/export/orders.xlsx",
    getBootstrap: async () => refreshBootstrap(),
    hasAccounts: async () => {
      const bootstrap = await ensureReady();
      return bootstrap.hasAdmins;
    },
    getCurrentAdmin: async () => {
      const bootstrap = await refreshBootstrap();
      return bootstrap.currentAdmin || null;
    },
    verifyLogin: async (login, password) => {
      const payload = await request("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          login: trimValue(login),
          password: trimValue(password),
        }),
      });

      bootstrapCache = {
        ...(bootstrapCache || {}),
        hasAdmins: true,
        currentAdmin: payload.admin,
      };

      return payload.admin;
    },
    logout: async () => {
      await request("/api/auth/logout", { method: "POST" });
      await refreshBootstrap();
    },
    getOrders: async () => {
      const payload = await request("/api/orders");
      return payload.orders || [];
    },
    saveOrder: async (order) => {
      const payload = await request("/api/orders", {
        method: "POST",
        body: JSON.stringify(order),
      });

      return payload.order;
    },
    getAccounts: async () => {
      const payload = await request("/api/admins");
      return payload.admins || [];
    },
    createAccount: async (login, password) => {
      const payload = await request("/api/admins", {
        method: "POST",
        body: JSON.stringify({
          login: trimValue(login),
          password: trimValue(password),
        }),
      });

      await refreshBootstrap();
      return payload.admin;
    },
    deleteAccount: async (login) => {
      await request(`/api/admins/${encodeURIComponent(normalizeLogin(login))}`, {
        method: "DELETE",
      });

      await refreshBootstrap();
    },
    updatePassword: async (login, password) => {
      await request("/api/admins/password", {
        method: "PATCH",
        body: JSON.stringify({
          login: trimValue(login),
          password: trimValue(password),
        }),
      });

      await refreshBootstrap();
    },
    updateOrderStatus: async (orderId, status) => {
      const payload = await request(`/api/orders/${encodeURIComponent(trimValue(orderId))}/status`, {
        method: "PATCH",
        body: JSON.stringify({
          status: trimValue(status),
        }),
      });

      return payload.order;
    },
  };

  init().catch(() => {
    // The page can still render; admin actions will show a server error when used.
  });
})();
