// находим форму с выбранными параметрами
const dcForm = document.querySelector("#dc_form");

// запускаем функцию formHandler на событие формы submit
dcForm.addEventListener("submit", formHandler);

function formHandler(event) {
  event.preventDefault();

  // удаляем прошлое содержимое тэга
  const divElementA = document.querySelector("#log_stream");
  divElementA.innerHTML = "";

  // забираем из radio элемента выбранный дата-цент
  function getSelectedRadio(Radios) {
    for (let radio of Radios) {
      if (radio.checked) {
        return radio.value;
      }
    }
  }

  let dcRadios = document.getElementsByName("DCRadios");
  const dc_name = getSelectedRadio(dcRadios);
  const selectedVlan = document.querySelector("#select-vlan").value;

  // устанавливаем соединение socket io
  socket = io.connect(
    location.protocol +
      "//" +
      document.domain +
      ":" +
      location.port +
      location.pathname
  );

  // послыаем soketio сообщение "start" серверу cо значением выбранного дата-центра из const dc_name
  // сервер услышит данное сообщение и запустит фунцию внутри себя за обработчиком "start"
  socket.emit("start", {
    dc: dc_name,
    vlan: selectedVlan,
  });

  // ловим сообщение от socketIO и создаем <pre> с текстом из soketIO
  socket.on("server_info_messages", function (msg) {
    // вызываем функцию colorLogs
    const logMsgtoDiv = colorLogs(msg.data);

    // добавляем раскрашенный лог в тэг <div>, обернутый в <pre>
    const pre = `<pre>${logMsgtoDiv["logMessage"]}</pre>`;

    // создаем линию <hr> и применяем к ней css class
    const hrLine = document.createElement("hr");
    hrLine.classList.add("hr-vertical-lines");

    const divElement = document.querySelector("#log_stream");
    divElement.insertAdjacentHTML("beforeend", pre);

    // добавляем горизонтальную линию после получения лога с уровнем SUCCESS
    if (logMsgtoDiv["level"] == "SUCCESS") {
      document.getElementById("log_stream").appendChild(hrLine);
    }

    // скролл к последнему элементу <pre>
    const lastChildElement = divElement.lastElementChild;
    lastChildElement?.scrollIntoView({ behavior: "smooth" });
  });

  // реализация работы progress bar
  let i = 0;
  socket.on("progressBarUpdate", function (msg) {
    const progressDiv = document.getElementById("progressBarDiv");

    if (selectedVlan == "ALL") {
      if (progressDiv.hasAttribute("hidden")) {
        progressDiv.removeAttribute("hidden");
      }
    }
    // текущий номер итерации progress bar, на это значение каждый раз умножается 1% ширины progress bar за итерацию
    i = i + 1;

    // значение 1%-ого заполенния progress bar
    let OneProgressHop = 100 / msg.total;

    // количество заполнения Progress bar за 1 вызов функции
    let currentHop = OneProgressHop * i;

    const progressP = document.getElementById("progressBarDoneInfo");
    const progressLine = document.getElementById("progressBarLine");

    progressP.textContent = `Выполнено ${i} из ${msg.total}`;

    // меняем полосу progress bar
    progressLine.setAttribute("aria-valuenow", currentHop);
    progressLine.setAttribute("style", `width:${currentHop}%`);
    progressLine.textContent = `${currentHop.toFixed(1)} %`;
  });

  socket.on("server_host_info_reply", function (msg) {
    // текущий vlan id
    let currentVlan = msg.statistics[0][1];

    // таблица, в которую выводим данные статистики сети
    let statisticTable = document.createElement("table");
    statisticTable.setAttribute("id", "statisticTable");

    let tbody_statisticTable = document.createElement("tbody");

    // заголовок таблицы
    statisticTable.createCaption().innerHTML = `<p class="lead">Статистика сетевого сегмента VLAN ${currentVlan}:</p>`;

    for (let item of msg.statistics) {
      let row = document.createElement("tr");

      for (let val of item) {
        let column = document.createElement("td");
        let text = document.createTextNode(val);
        column.appendChild(text);
        row.appendChild(column);
      }
      tbody_statisticTable.appendChild(row);
    }
    statisticTable.appendChild(tbody_statisticTable);
    statisticTable.classList.add(
      "ztable",
      "mx-auto",
      "mx-2",
      "my-1",
      "caption-top",
      "my-sm-3"
    );

    // таблица, в которую выводим данные о хостах сети
    let hostsTable = document.createElement("table");
    let tbody = document.createElement("tbody");
    let thead = document.createElement("thead");

    // заголовок таблицы
    hostsTable.createCaption().innerHTML = `<p class="lead">Хосты сетевого сегмента VLAN ${currentVlan}:</p>`;

    // шапка таблицы
    const headers = ["IPv4 address", "hostname", "MAC address", "vendor"];
    hostsTable.appendChild(thead);
    for (let header of headers) {
      thead
        .appendChild(document.createElement("th"))
        .appendChild(document.createTextNode(header));
    }

    // создаем элементы таблицы и наполняем их
    for (let item of msg.hosts_data) {
      let row = document.createElement("tr");

      for (let val of item) {
        let column = document.createElement("td");
        let text = document.createTextNode(val);
        column.appendChild(text);
        row.appendChild(column);
      }
      tbody.appendChild(row);
    }
    hostsTable.appendChild(tbody);
    hostsTable.classList.add(
      "ztable",
      "mx-auto",
      "mx-2",
      "my-1",
      "caption-top",
      "my-sm-3"
    );

    // добавляем таблицу statisticTable на страницу
    document.getElementById("log_stream").appendChild(statisticTable);

    // добавляем таблицу hostsTable на страницу
    document.getElementById("log_stream").appendChild(hostsTable);
  });

  socket.on("closeConnection", function () {
    // закрываем socket io соединение
    socket.close();
  });
}

// кнопка обновления информации о vlan id
const updateVlanInfoButton = document.querySelector("#updateVlanInfo");

// <span>, где находится имя кнопки
const spanUpdateButton = document.querySelector("#span-update-button-name");

updateVlanInfoButton.addEventListener("click", function () {
  // устанавливаем соединение socket io
  socket = io.connect(
    location.protocol +
      "//" +
      document.domain +
      ":" +
      location.port +
      location.pathname
  );
  socket.emit("updateVlanInfo");

  // по нажатию кнопки добавляем стиль спинера на кнопку и делаем её неактивной
  // создаем констуркцию из <span> для реализации спинера внутри кнопки
  const spanForSpinnerButton1 = document.createElement("span");

  // Добавляем стили и атрибуты к <span>
  spanForSpinnerButton1.classList.add("spinner-border", "spinner-border-sm");
  spanForSpinnerButton1.setAttribute("aria-hidden", "true");
  spanForSpinnerButton1.setAttribute("id", "span-active-spinner");

  // переключаем кнопку в disabled и вставляем в <button> тэг <span>
  updateVlanInfoButton.toggleAttribute("disabled");
  updateVlanInfoButton.append(spanForSpinnerButton1);
  spanUpdateButton.textContent = "Обновление";

  socket.on("update_vlan_info_reply", function (msg) {
    document.querySelector("#vlan_relevance").textContent = msg;

    // после получения данных о vlan id убираем <span> со spinner и делаем кнопку снова активной
    updateVlanInfoButton.toggleAttribute("disabled");
    spanUpdateButton.textContent = "Обновить";
    const spanSprinner = document.querySelector("#span-active-spinner");
    spanSprinner.remove();
  });
});
