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
					<text @longpress="copyText(item.content)">{{ item.content }}</text>
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
			lastMsgId: ''
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
			const BACKEND_URL = 'http://10.60.145.177:8000/chat'; 

			uni.request({
				url: BACKEND_URL,
				method: 'POST',
				header: { 'Content-Type': 'application/json' },
				data: {
					content: q,
					chapter_id: this.chapterId
				},
				success: (res) => {
					this.isTyping = false;
					if (res.data && res.data.reply) {
						this.chatList.push({ role: 'ai', content: res.data.reply });
					} else {
						this.chatList.push({ role: 'ai', content: '助教由于网络原因暂时无法回答。' });
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