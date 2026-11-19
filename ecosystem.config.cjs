// PM2 Ecosystem Config — Runs Both Bots from the Same Codebase
// Usage:
//   pm2 start ecosystem.config.cjs
//   pm2 save
//   pm2 status

module.exports = {
  apps: [
    {
      name: "exabyte-bot1",
      script: "./.venv/bin/python",
      args: "-m exabyte_bot.main",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        ENV_FILE: ".env",
        STORE_NAME: "Exabyte Digital Store",
        REQUIRED_CHANNEL: "",
        REQUIRED_CHANNEL_URL: "",
        BOT_DOMAIN: "tgbot.lhpvpn.online",
        WEB_HOST: "127.0.0.1",
        WEB_PORT: "8082",
        DATA_DIR: "./data",
      },
    },
    {
      name: "outlineplus-bot2",
      script: "./.venv/bin/python",
      args: "-m exabyte_bot.main",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      env: {
        ENV_FILE: ".env.bot2",
        STORE_NAME: "Outline Plus MM",
        REQUIRED_CHANNEL: "@outlineplusmm",
        REQUIRED_CHANNEL_URL: "https://t.me/outlineplusmm",
        BOT_DOMAIN: "tgbot2.lhpvpn.online",
        SUPPORT_URL: "https://t.me/mlbbstorycca",
        WEB_HOST: "127.0.0.1",
        WEB_PORT: "8081",
        DATA_DIR: "./data_bot2",
      },
    },
  ],
};
