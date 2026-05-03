const menuToggle = document.querySelector(".menu-toggle");
const siteNav = document.querySelector(".site-nav");

if (menuToggle && siteNav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = siteNav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });
}

const phoneInput = document.querySelector("#phoneInput");
const cargoField = document.querySelector("#cargoField");
const form = document.querySelector("#transportForm");
const result = document.querySelector("#formResult");
const successPopup = document.querySelector("#successPopup");
const successPopupClose = document.querySelector("#successPopupClose");
const successPopupTitle = document.querySelector("#successPopupTitle");
const successPopupText = document.querySelector("#successPopupText");
const successPopupBadge = document.querySelector(".success-popup-badge");
let successPopupTimer = null;

const formatPhoneNumber = (value) => {
  let digits = value.replace(/\D/g, "");

  if (!digits) {
    return "";
  }

  if (digits.startsWith("8")) {
    digits = `7${digits.slice(1)}`;
  }

  if (!digits.startsWith("7")) {
    digits = `7${digits.slice(0)}`;
  }

  digits = digits.slice(0, 11);

  if (digits.length === 1) {
    return "+7";
  }

  let output = "+7";

  if (digits.length > 1) {
    output += ` (${digits.slice(1, 4)}`;
  }

  if (digits.length > 4) {
    output += ")";
  }

  if (digits.length > 4) {
    output += ` ${digits.slice(4, 7)}`;
  }

  if (digits.length > 7) {
    output += `-${digits.slice(7, 9)}`;
  }

  if (digits.length > 9) {
    output += `-${digits.slice(9, 11)}`;
  }

  return output;
};

if (phoneInput) {
  phoneInput.addEventListener("focus", () => {
    if (!phoneInput.value) {
      phoneInput.value = "+7";
    }
  });

  phoneInput.addEventListener("input", () => {
    phoneInput.value = formatPhoneNumber(phoneInput.value);
  });

  phoneInput.addEventListener("keydown", (event) => {
    const blockedKeys = ["e", "E", "+", "-", ".", ","];

    if (blockedKeys.includes(event.key)) {
      event.preventDefault();
    }
  });

  phoneInput.addEventListener("blur", () => {
    if (phoneInput.value === "+7") {
      phoneInput.value = "";
    }
  });
}

if (cargoField) {
  cargoField.addEventListener("input", () => {
    cargoField.scrollTop = cargoField.scrollHeight;
  });
}

const closeSuccessPopup = () => {
  if (!successPopup) {
    return;
  }

  successPopup.hidden = true;

  if (successPopupTimer) {
    window.clearTimeout(successPopupTimer);
    successPopupTimer = null;
  }
};

const openSuccessPopup = () => {
  if (!successPopup) {
    return;
  }

  successPopup.hidden = false;

  if (successPopupTimer) {
    window.clearTimeout(successPopupTimer);
  }

  successPopupTimer = window.setTimeout(() => {
    closeSuccessPopup();
  }, 3500);
};

const setPopupState = (title, text, type = "success") => {
  if (!successPopupTitle || !successPopupText || !successPopupBadge) {
    return;
  }

  successPopupTitle.textContent = title;
  successPopupText.textContent = text;
  successPopupBadge.textContent = type === "success" ? "Успешно" : "Ошибка";
  successPopup.classList.toggle("is-error", type === "error");
};

if (successPopup && successPopupClose) {
  successPopupClose.addEventListener("click", () => {
    closeSuccessPopup();
  });

  successPopup.addEventListener("click", (event) => {
    if (event.target === successPopup) {
      closeSuccessPopup();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !successPopup.hidden) {
      closeSuccessPopup();
    }
  });
}

if (form && result) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const formData = new FormData(form);
    const customer = formData.get("customer");
    const phone = formData.get("phone");
    const truckType = formData.get("truckType");
    const dateTime = formData.get("dateTime");
    const cargo = formData.get("cargo");

    try {
      await window.GazelStore.saveOrder({
        customer: String(customer || ""),
        phone: String(phone || ""),
        truckType: String(truckType || ""),
        dateTime: String(dateTime || ""),
        cargo: String(cargo || ""),
      });

      result.innerHTML = "";
      result.classList.remove("visible");

      form.reset();

      if (phoneInput) {
        phoneInput.value = "";
      }

      if (cargoField) {
        cargoField.value = "";
        cargoField.scrollTop = 0;
      }

      setPopupState("Заявка отправлена", "Можно закрыть окно и оформить следующую перевозку.");
      openSuccessPopup();
    } catch (error) {
      setPopupState("Не удалось отправить заявку", error.message || "Повторите попытку ещё раз.", "error");
      openSuccessPopup();
    }
  });
}
