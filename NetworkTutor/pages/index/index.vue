<template>
	<view class="container">
		<scroll-view 
			class="chat-box" 
			scroll-y="true" 
			:scroll-into-view="lastMsgId" 
			scroll-with-animation
		>
			<view v-for="(item, index) in chatList" :key="index" :id="'msg-' + index" :class="['msg-item', item.role]">
			    <view class="bubble">
			        <view v-if="item.role === 'ai' && item.think" class="think-container">
			            <view class="think-title" @click="item.showThink = !item.showThink">
			                <text class="icon">{{ item.showThink ? '▼' : '▶' }}</text> 
			                已深度思考（点击{{ item.showThink ? '收起' : '展开' }}）
			            </view>
			            <view v-if="item.showThink" class="think-content">{{ item.think }}</view>
			        </view>
			
			        <text class="main-content" @longpress="copyText(item.content)">{{ item.content }}</text>
			
			        <view v-if="item.role === 'ai' && item.sources && item.sources.length > 0" class="sources-container">
			            <view class="source-header">参考来源：</view>
			            <view v-for="(src, sIndex) in item.sources" :key="sIndex" class="source-item">
			                [{{ sIndex + 1 }}] 第{{ src.chapter }}章：{{ src.path }}
			            </view>
			        </view>
			    </view>
			</view>
			
			<view v-if="isTyping" class="msg-item ai" id="msg-typing">
				<view class="bubble">
					<view class="typing-dots">助教正在翻阅教材...</view>
				</view>
			</view>
			
			<view style="height: 30rpx;"></view>
		</scroll-view>

		<view class="input-area">
			<view class="chapter-tag" v-if="chapterId">
				第{{ chapterId }}章
				<text class="close-tag" @click="chapterId = null">×</text>
			</view>
			<view class="input-row">
				<textarea 
					class="input" 
					v-model="userMsg" 
					placeholder="问问助教..." 
					auto-height 
					fixed
					:cursor-spacing="20"
					@confirm="sendMsg" 
				/>
				<button class="btn" @click="sendMsg" :disabled="isTyping || !userMsg">发送</button>
			</view>
		</view>
	</view>
</template>

<script>
export default {
	data() {
		return {
			userMsg: '',
			isTyping: false,
			chatList: [{ role: 'ai', content: '你好！我是计网助教。你可以扫描教材二维码进入指定章节，或者直接提问。' }],
			chapterId: null,
			lastMsgId: '',
			showSourceModal: false, // 控制弹窗显示
			sourceDetail: ''// 存储点击的原文内容
		}
	},
	onLoad(options) {
		// --- 1. 核心：解析扫码参数 ---
		let cid = null;
		if (options.chapter) {
			cid = options.chapter; // 普通调试：?chapter=3
		} else if (options.scene) {
			const scene = decodeURIComponent(options.scene);
			// 假设格式为 id=3
			cid = scene.split('=')[1]; 
		}

		if (cid) {
			this.chapterId = cid;
			this.chatList.push({ 
				role: 'ai', 
				content: `📖 已进入第 ${cid} 章专项辅导模式。` 
			});
			this.scrollToBottom();
		}
	},
	methods: {
		async sendMsg() {
			if (!this.userMsg || this.isTyping) return;
			
			const q = this.userMsg;
			this.chatList.push({ role: 'user', content: q });
			this.userMsg = '';
			this.isTyping = true;
			this.scrollToBottom();

			// --- 2. 核心：请求你的 FastAPI 后端 ---
			// 注意：真机调试需将 127.0.0.1 换成你电脑的局域网 IP (如 192.168.1.5)
			const BACKEND_URL = 'http://10.60.145.177:8000/api/rag/ask';

			uni.request({
				url: BACKEND_URL,
				method: 'POST',
				header: { 'Content-Type': 'application/json' },
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
				            // --- 核心逻辑：只要有结尾标签，就进行切分 ---
				            if (startIdx !== -1) {
				                // 正常的完整情况
				                thinkPart = raw.substring(startIdx + startTag.length, endIdx).trim();
				            } else {
				                // 只有结尾的情况：从开头一直截取到结尾标签之前
				                thinkPart = raw.substring(0, endIdx).trim();
				            }
				            // 正文始终是结尾标签之后的内容
				            finalContent = raw.substring(endIdx + endTag.length).trim();
				        }
				
				        this.chatList.push({
				            role: 'ai',
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
					uni.showToast({ title: '连接服务器失败', icon: 'none' });
				}
			});
		},
		scrollToBottom() {
			this.$nextTick(() => {
				const lastIndex = this.chatList.length - 1;
				this.lastMsgId = 'msg-' + lastIndex;
				// 如果正在思考，则滚到思考气泡
				if (this.isTyping) {
					this.lastMsgId = 'msg-typing';
				}
			});
		},
		copyText(text) {
			uni.setClipboardData({
				data: text,
				success: () => uni.showToast({ title: '已复制' })
			});
		}
	}
}
</script>

<style>
/* 思考块样式 */
.think-container {
    background: #f0f0f0;
    border-radius: 8rpx;
    padding: 12rpx;
    margin-bottom: 15rpx;
    font-size: 24rpx;
    color: #666;
    border-left: 6rpx solid #ccc;
}
.think-title { font-weight: bold; margin-bottom: 8rpx; display: flex; align-items: center; }
.think-content { line-height: 1.4; border-top: 1rpx solid #ddd; padding-top: 8rpx; }

/* 来源块样式 */
.sources-container {
    margin-top: 20rpx;
    padding-top: 15rpx;
    border-top: 1rpx dashed #eee;
}
.source-header { font-size: 22rpx; color: #999; margin-bottom: 6rpx; }
.source-item {
    font-size: 22rpx;
    color: #0288d1;
    margin-bottom: 4rpx;
    display: block;
    word-break: break-all;
}
.main-content { font-size: 30rpx; white-space: pre-wrap; }
.container { display: flex; flex-direction: column; height: 100vh; background: #f7f7f7; }
.chat-box { flex: 1; padding: 20rpx 40rpx; overflow: hidden; }
.msg-item { display: flex; margin-bottom: 30rpx; transition: all 0.3s; }
.bubble { padding: 18rpx 24rpx; border-radius: 16rpx; max-width: 75%; font-size: 30rpx; line-height: 1.5; }
.user { flex-direction: row-reverse;width: 100%; }
.user .bubble { background: #07c160; color: #fff; margin-right:50rpx;margin-left: 20rpx; }
.ai .bubble { background: #ffffff; color: #333; margin-right: 20rpx; border: 1rpx solid #e0e0e0; }

.input-area { background: #fff; border-top: 1rpx solid #eee; padding: 20rpx; padding-bottom: calc(20rpx + env(safe-area-inset-bottom)); }
.chapter-tag { display: inline-block; background: #e1f5fe; color: #0288d1; font-size: 22rpx; padding: 4rpx 12rpx; border-radius: 6rpx; margin-bottom: 10rpx; }
.close-tag { margin-left: 10rpx; font-weight: bold; }
.input-row { display: flex; align-items: flex-end; }
.input { flex: 1; min-height: 70rpx; max-height: 200rpx; background: #f2f2f2; padding: 15rpx 20rpx; border-radius: 12rpx; font-size: 30rpx; }
.btn { width: 120rpx; height: 75rpx; line-height: 75rpx; margin-left: 20rpx; background: #07c160; color: #fff; font-size: 28rpx; border-radius: 12rpx; border: none; }
.btn[disabled] { background: #e0e0e0; color: #999; }

.typing-dots { font-style: italic; color: #999; font-size: 26rpx; }
</style>