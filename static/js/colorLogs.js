function colorLogs(logStr) {
    let logLevelColor;
    let logLevelBackgroundColor;
    const regexObj =
      /(?<date>.+)\|(?<level>.+)\|(?<username>.+)\|(?<message>.+)/g;

    const regexObj2 =
      /(?<date>.+)\|(?<level>.+)\|(?<username>.+)\|(?<message>[\s\S]+)/g;

    let regexResult = regexObj.exec(logStr);

    if (regexResult.groups.level.trim() == "DEBUG") {
      logLevelColor = "DarkKhaki";

    } else if (regexResult.groups.level.trim() == "INFO") {
      logLevelColor = "MediumOrchid";

    } else if (regexResult.groups.level.trim() == "SUCCESS") {
      logLevelColor = "Black";
      logLevelBackgroundColor = "LightGreen";

    } else if (regexResult.groups.level.trim() == "WARNING") {
      logLevelColor = "Black";
      logLevelBackgroundColor = "Yellow";

    } else if (regexResult.groups.level.trim() == "ERROR") {
      logLevelColor = "Yellow";
      logLevelBackgroundColor = "Orange";

    } else if (regexResult.groups.level.trim() == "CRITICAL") {
      logLevelColor = "Yellow";
      logLevelBackgroundColor = "Salmon";
    }

    let logLevel;
    let Message;

    if (["WARNING", "ERROR", "CRITICAL"].includes(regexResult.groups.level.trim())) {
      logLevel = `<span style="background-color:${logLevelBackgroundColor}; color: ${logLevelColor}; font-weight:bold">${regexResult.groups.level.trim()}</span>`;
      Message = `<span style="background-color:${logLevelBackgroundColor}">${regexResult.groups.message.trim()}</span>`;
    }

    else if (["DEBUG", "INFO"].includes(regexResult.groups.level.trim())) {
      logLevel = `<span style="color:${logLevelColor}; font-weight:bold">${regexResult.groups.level.trim()}</span>`;
      Message = `<span>${regexResult.groups.message.trim()}</span>`;
    }

    else {
      logLevel = `<span style="background-color:${logLevelBackgroundColor}; color: ${logLevelColor}; font-weight:bold">${regexResult.groups.level.trim()}</span>`;
      Message = `<span>${regexResult.groups.message.trim()}</span>`;
    }

    let logData = `<span style="color:MediumSlateBlue">${regexResult.groups.date.trim()}</span>`;
    let logUsername = `<span style="color:Sienna">${regexResult.groups.username.trim()}</span>`;

    let logOutputMsg = logData + " | " + logLevel + " | " + logUsername + " | " + Message;

    let logOutput = {
      level: regexResult.groups.level.trim(),
      logMessage: logOutputMsg,
    };
    return logOutput;
  }
