"use strict";
const common_vendor = require("../../common/vendor.js");
const _sfc_main = {
  data() {
    return {
      userMsg: "",
      isTyping: false,
      chatList: [{ role: "ai", content: "你好！我是计网助教。你可以扫描教材二维码进入指定章节，或者直接提问。" }],
      chapterId: null,
      lastMsgId: "",
      showSourceModal: false,
      // 控制弹窗显示
      sourceDetail: ""
      // 存储点击的原文内容
    };
  },
  onLoad(options) {
    let cid = null;
    if (options.chapter) {
      cid = options.chapter;
    } else if (options.scene) {
      const scene = decodeURIComponent(options.scene);
      cid = scene.split("=")[1];
    }
    if (cid) {
      this.chapterId = cid;
      this.chatList.push({
        role: "ai",
        content: `📖 已进入第 ${cid} 章专项辅导模式。`
      });
      this.scrollToBottom();
    }
  },
  methods: {
    async sendMsg() {
      if (!this.userMsg || this.isTyping)
        return;
      const q = this.userMsg;
      this.chatList.push({ role: "user", content: q });
      this.userMsg = "";
      this.isTyping = true;
      this.scrollToBottom();
      const BACKEND_URL = "http://10.60.145.177:8000/api/rag/ask";
      common_vendor.index.request({
        url: BACKEND_URL,
        method: "POST",
        header: { "Content-Type": "application/json" },
        data: {
          // 1. 匹配后端字段名：question
          question: q,
          // 2. 匹配后端字段名：chapter。如果没有扫码则传 "all"，否则转为字符串
          chapter: this.chapterId ? String(this.chapterId) : "all",
          // 3. 增加 top_k 参数，控制检索精度
          top_k: 4
        },
        success: (res) => {
          this.isTyping = false;
          if (res.data && res.data.answer) {
            let raw = String(res.data.answer);
            let thinkPart = "";
            let finalContent = raw;
            const lowerRaw = raw.toLowerCase();
            const startTag = "<think>";
            const endTag = "</think>";
            const startIdx = lowerRaw.indexOf(startTag);
            const endIdx = lowerRaw.indexOf(endTag);
            if (endIdx !== -1) {
              if (startIdx !== -1) {
                thinkPart = raw.substring(startIdx + startTag.length, endIdx).trim();
              } else {
                thinkPart = raw.substring(0, endIdx).trim();
              }
              finalContent = raw.substring(endIdx + endTag.length).trim();
            }
            this.chatList.push({
              role: "ai",
              think: thinkPart,
              showThink: false,
              content: finalContent || "回答生成完毕。",
              sources: res.data.sources || []
            });
          }
          this.scrollToBottom();
        },
        fail: (err) => {
          this.isTyping = false;
          common_vendor.index.showToast({ title: "连接服务器失败", icon: "none" });
        }
      });
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const lastIndex = this.chatList.length - 1;
        this.lastMsgId = "msg-" + lastIndex;
        if (this.isTyping) {
          this.lastMsgId = "msg-typing";
        }
      });
    },
    copyText(text) {
      common_vendor.index.setClipboardData({
        data: text,
        success: () => common_vendor.index.showToast({ title: "已复制" })
      });
    }
  }
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return common_vendor.e({
    a: common_vendor.f($data.chatList, (item, index, i0) => {
      return common_vendor.e({
        a: item.role === "ai" && item.think
      }, item.role === "ai" && item.think ? common_vendor.e({
        b: common_vendor.t(item.showThink ? "▼" : "▶"),
        c: common_vendor.t(item.showThink ? "收起" : "展开"),
        d: common_vendor.o(($event) => item.showThink = !item.showThink, index),
        e: item.showThink
      }, item.showThink ? {
        f: common_vendor.t(item.think)
      } : {}) : {}, {
        g: common_vendor.t(item.content),
        h: common_vendor.o(($event) => $options.copyText(item.content), index),
        i: item.role === "ai" && item.sources && item.sources.length > 0
      }, item.role === "ai" && item.sources && item.sources.length > 0 ? {
        j: common_vendor.f(item.sources, (src, sIndex, i1) => {
          return {
            a: common_vendor.t(sIndex + 1),
            b: common_vendor.t(src.chapter),
            c: common_vendor.t(src.path),
            d: sIndex
          };
        })
      } : {}, {
        k: index,
        l: "msg-" + index,
        m: common_vendor.n(item.role)
      });
    }),
    b: $data.isTyping
  }, $data.isTyping ? {} : {}, {
    c: $data.lastMsgId,
    d: $data.chapterId
  }, $data.chapterId ? {
    e: common_vendor.t($data.chapterId),
    f: common_vendor.o(($event) => $data.chapterId = null)
  } : {}, {
    g: common_vendor.o((...args) => $options.sendMsg && $options.sendMsg(...args)),
    h: $data.userMsg,
    i: common_vendor.o(($event) => $data.userMsg = $event.detail.value),
    j: common_vendor.o((...args) => $options.sendMsg && $options.sendMsg(...args)),
    k: $data.isTyping || !$data.userMsg
  });
}
const MiniProgramPage = /* @__PURE__ */ common_vendor._export_sfc(_sfc_main, [["render", _sfc_render]]);
wx.createPage(MiniProgramPage);
//# sourceMappingURL=../../../.sourcemap/mp-weixin/pages/index/index.js.map
