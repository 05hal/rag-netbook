"use strict";
const common_vendor = require("../../common/vendor.js");
const _sfc_main = {
  data() {
    return {
      userMsg: "",
      isTyping: false,
      chatList: [{ role: "ai", content: "你好！我是计网助教，Demo测试中。" }],
      // 教材内容
      textbookData: "ADSL是非对称数字用户环路，采用频分复用技术。钱天白教授发出了中国第一封国际电子邮件。"
    };
  },
  methods: {
    async sendMsg() {
      if (!this.userMsg || this.isTyping)
        return;
      const q = this.userMsg;
      this.chatList.push({ role: "user", content: q });
      this.userMsg = "";
      this.isTyping = true;
      const API_URL = "https://api.siliconflow.cn/v1/chat/completions";
      const API_KEY = "sk-lyahiincthnowhyvibyigzttrgjomivpsojejxausgojgaej";
      const MODEL_NAME = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B";
      common_vendor.index.request({
        url: API_URL,
        method: "POST",
        header: {
          "Authorization": "Bearer " + API_KEY,
          "Content-Type": "application/json"
        },
        data: {
          model: MODEL_NAME,
          messages: [
            { "role": "system", "content": "你是一个计网助教，请根据教材回答：" + this.textbookData },
            { "role": "user", "content": q }
          ],
          stream: false
          // Demo 暂时关闭流式传输，方便逻辑处理
        },
        success: (res) => {
          this.isTyping = false;
          if (res.data && res.data.choices) {
            let answer = res.data.choices[0].message.content;
            if (answer.includes("</think>")) {
              const parts = answer.split("</think>");
              answer = parts[parts.length - 1].trim();
            } else {
              answer = answer.replace(/<think>[\s\S]*/g, "").trim();
            }
            if (!answer)
              answer = "正在组织语言...";
            this.chatList.push({ role: "ai", content: answer });
          }
        },
        fail: (err) => {
          this.isTyping = false;
          common_vendor.index.__f__("error", "at pages/index/index.vue:87", "请求失败", err);
          common_vendor.index.showToast({ title: "连接服务器失败", icon: "none" });
        }
      });
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return common_vendor.e({
    a: common_vendor.f($data.chatList, (item, index, i0) => {
      return {
        a: common_vendor.t(item.content),
        b: index,
        c: common_vendor.n(item.role)
      };
    }),
    b: $data.isTyping
  }, $data.isTyping ? {} : {}, {
    c: common_vendor.o((...args) => $options.sendMsg && $options.sendMsg(...args)),
    d: $data.userMsg,
    e: common_vendor.o(($event) => $data.userMsg = $event.detail.value),
    f: common_vendor.o((...args) => $options.sendMsg && $options.sendMsg(...args)),
    g: $data.isTyping
  });
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/index/index.js.map
