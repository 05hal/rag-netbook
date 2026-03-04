<template>
	<view class="container">
		<scroll-view class="chat-box" scroll-y="true">
			<view v-for="(item, index) in chatList" :key="index" :class="['msg-item', item.role]">
				<view class="bubble">
					<text>{{ item.content }}</text>
				</view>
			</view>
			<view v-if="isTyping" class="msg-item ai">
				<view class="bubble"><text>正在思考...</text></view>
			</view>
		</scroll-view>

		<view class="input-area">
			<input class="input" v-model="userMsg" placeholder="问问计网助教..." @confirm="sendMsg" />
			<button class="btn" @click="sendMsg" :disabled="isTyping">发送</button>
		</view>
	</view>
</template>

<script>
export default {
	data() {
		return {
			userMsg: '',
			isTyping: false,
			chatList: [{ role: 'ai', content: '你好！我是计网助教，Demo测试中。' }],
			// 教材内容
			textbookData: "ADSL是非对称数字用户环路，采用频分复用技术。钱天白教授发出了中国第一封国际电子邮件。"
		}
	},
	methods: {
		async sendMsg() {
			if (!this.userMsg || this.isTyping) return;
			const q = this.userMsg;
			this.chatList.push({ role: 'user', content: q });
			this.userMsg = '';
			this.isTyping = true;

			// --- 硅基流动 API 配置 ---
			// 1. 这里的 URL 换成硅基流动的地址
			const API_URL = 'https://api.siliconflow.cn/v1/chat/completions';
			// 2. 这里的 Key 换成你在硅基流动后台申请的 API Key
			const API_KEY = 'sk-lyahiincthnowhyvibyigzttrgjomivpsojejxausgojgaej'; 
			// 3. 选择模型，硅基流动支持很多免费模型（如 deepseek-ai/DeepSeek-V2-Chat 等，具体看其官网免费列表）
			const MODEL_NAME = 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B'; 

			uni.request({
				url: API_URL,
				method: 'POST',
				header: {
					'Authorization': 'Bearer ' + API_KEY,
					'Content-Type': 'application/json'
				},
				data: {
					model: MODEL_NAME,
					messages: [
						{ "role": "system", "content": "你是一个计网助教，请根据教材回答：" + this.textbookData },
						{ "role": "user", "content": q }
					],
					stream: false // Demo 暂时关闭流式传输，方便逻辑处理
				},
				success: (res) => {
				    this.isTyping = false;
				    if (res.data && res.data.choices) {
				        let answer = res.data.choices[0].message.content;
				        
				        // --- 更加鲁棒的过滤逻辑 ---
				        if (answer.includes('</think>')) {
				            // 如果包含结束标签，我们直接截取结束标签之后的所有内容
				            // split('</think>') 会把字符串分成 [思考部分, 正式回答部分]
				            const parts = answer.split('</think>');
				            answer = parts[parts.length - 1].trim(); 
				        } else {
				            // 如果连结束标签都没有，但有开始标签，说明还没思考完就被截断了
				            answer = answer.replace(/<think>[\s\S]*/g, '').trim();
				        }
				        
				        // 如果截取后发现内容为空（说明还没开始出正式答案），可以给个提示
				        if(!answer) answer = "正在组织语言...";
				        
				        this.chatList.push({ role: 'ai', content: answer });
				    }
				},
				fail: (err) => {
					this.isTyping = false;
					console.error("请求失败", err);
					uni.showToast({ title: '连接服务器失败', icon: 'none' });
				}
			});
		}
	}
}
</script>

<style>
/* 保持你原来的样式不变 */
.container { display: flex; flex-direction: column; height: 100vh; background: #f5f5f5; }
.chat-box { flex: 1; padding: 20rpx; overflow: hidden; }
.msg-item { display: flex; margin-bottom: 30rpx; }
.bubble { padding: 20rpx; border-radius: 10rpx; max-width: 70%; word-break: break-all; font-size: 28rpx; }
.user { flex-direction: row-reverse; }
.user .bubble { background: #95ec69; margin-left: 20rpx; }
.ai .bubble { background: #ffffff; margin-right: 20rpx; }
.input-area { display: flex; padding: 20rpx; background: #fff; border-top: 1rpx solid #ddd; padding-bottom: calc(20rpx + env(safe-area-inset-bottom)); }
.input { flex: 1; height: 80rpx; border: 1rpx solid #ccc; padding: 0 20rpx; border-radius: 8rpx; background: #fff; }
.btn { width: 140rpx; height: 80rpx; line-height: 80rpx; margin-left: 20rpx; background: #07c160; color: #fff; font-size: 26rpx; padding: 0; }
.btn[disabled] { background: #ccc; }
</style>