#!/usr/bin/env node

/**
 * 成语Wordle 前端 JS 混淆脚本
 * 功能：
 * 1. 替换 API baseURL 和 token
 * 2. 添加反调试代码
 * 3. 混淆 JS 代码
 * 4. 输出替换原文件
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const crypto = require('crypto');

const JavaScriptObfuscator = require('javascript-obfuscator');

// 目标文件路径
const TARGET_FILE = path.join(__dirname, '..', 'client', 'js', 'indexScript.js');

// 创建 readline 接口
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

// 提问函数封装
function question(prompt) {
    return new Promise((resolve) => {
        rl.question(prompt, (answer) => resolve(answer.trim()));
    });
}

async function main() {
    console.log('=== 成语Wordle JS 混淆工具 ===\n');

    // 1. 获取用户输入
    const baseUrl = await question('请输入 API Base URL（不含 /api，直接回车保持默认 127.0.0.1:8000）: ');
    const token = await question('请输入 API Token（原始字符串，不是sha256哈希！直接回车保持默认 test-token）: ');

    console.log('\n正在处理...');

    // 2. 读取原始 JS 文件
    if (!fs.existsSync(TARGET_FILE)) {
        console.error('错误：找不到文件', TARGET_FILE);
        process.exit(1);
    }

    let jsCode = fs.readFileSync(TARGET_FILE, 'utf8');

    // 3. 替换 baseURL
    const defaultBaseUrl = '127.0.0.1:8000';
    if (baseUrl) {
        // 处理用户输入：兼容多种写法
        let processedBaseUrl = baseUrl.trim();
        // 移除 http:// 或 https:// 协议头（兼容带协议的输入）
        processedBaseUrl = processedBaseUrl.replace(/^https?:\/\//i, '');
        // 移除尾部斜杠（兼容末尾带斜杠的输入）
        processedBaseUrl = processedBaseUrl.replace(/\/+$/, '');

        console.log(`→ 替换 API 地址: ${defaultBaseUrl} → ${processedBaseUrl}`);
        // 替换所有出现的地方
        jsCode = jsCode.split(`//${defaultBaseUrl}`).join(`//${processedBaseUrl}`);
    } else {
        console.log(`→ 保持默认 API 地址: ${defaultBaseUrl}`);
    }

    // 4. 替换 token - 修复bug：使用正则匹配完整的 'Bearer xxx' 格式
    const defaultToken = 'test-token';
    const actualToken = token || defaultToken;

    // 匹配模式：'Bearer <任意token>'
    const bearerPattern = /'Bearer ([^']+)'/g;
    const matches = jsCode.match(bearerPattern) || [];
    console.log(`→ 找到 ${matches.length} 处 Bearer Token 配置`);

    // 执行替换
    jsCode = jsCode.replace(bearerPattern, `'Bearer ${actualToken}'`);

    if (token) {
        console.log(`→ 替换 Token: ${defaultToken} → ${actualToken}`);

        // 验证替换是否成功
        const newMatches = jsCode.match(bearerPattern) || [];
        const replacedOk = newMatches.length === matches.length &&
            newMatches.every(m => m === `'Bearer ${actualToken}'`);

        if (replacedOk) {
            console.log(`→ 验证：所有 ${newMatches.length} 处 Token 已替换成功 ✓`);
        } else {
            console.log(`→ ⚠️  警告：Token替换可能不完整，请手动检查！`);
        }

        // 计算并显示sha256，方便用户添加到后端
        const tokenHash = crypto.createHash('sha256').update(actualToken).digest('hex');
        console.log(`  注意：请确保后端 token-sha256.txt 文件中已添加该token的sha256哈希值`);
        console.log(`  该Token的SHA256值（需添加到后端合法列表）: ${tokenHash}`);
    } else {
        console.log(`→ 保持默认 Token: ${defaultToken}`);
        console.log(`  对应的SHA256值: 4c5dc9b7708905f77f5e5d16316b5dfb425e68cb326dcd55a860e90a7707031e`);
    }

    // 5. 添加反调试代码
    const antiDebugCode = `
// ===== 反调试保护 =====
(function() {
    function antiDebug() {
        // 陷阱1：检测开发者工具
        const startTime = new Date();
        debugger;
        const endTime = new Date();
        if (endTime - startTime > 100) {
            document.body.innerHTML = '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:99999;font-family:sans-serif;"><h1 style="color:var(--primary);font-size:2em;margin-bottom:1rem;">检测到开发者工具</h1><p style="color:var(--text-secondary);">请关闭开发者工具后刷新页面</p></div>';
            return;
        }

        // 陷阱2：定时检测调试器
        setInterval(function() {
            const start = performance.now();
            debugger;
            const end = performance.now();
            if (end - start > 100) {
                document.body.innerHTML = '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:99999;font-family:sans-serif;"><h1 style="color:var(--primary);font-size:2em;margin-bottom:1rem;">检测到调试器</h1><p style="color:var(--text-secondary);">请关闭调试工具后刷新页面</p></div>';
            }
        }, 1000);

        // 陷阱3：禁止右键
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            return false;
        });

        // 陷阱4：禁止某些快捷键
        document.addEventListener('keydown', function(e) {
            // F12
            if (e.key === 'F12') {
                e.preventDefault();
                return false;
            }
            // Ctrl+Shift+I / Ctrl+Shift+J / Ctrl+Shift+C
            if (e.ctrlKey && e.shiftKey && ['I', 'J', 'C'].includes(e.key.toUpperCase())) {
                e.preventDefault();
                return false;
            }
            // Ctrl+U
            if (e.ctrlKey && e.key.toUpperCase() === 'U') {
                e.preventDefault();
                return false;
            }
        });

        // 陷阱5：console 清空干扰
        const originalLog = console.log;
        console.log = function() {};
        console.warn = function() {};
        console.info = function() {};
        console.error = function() {};
        setInterval(function() {
            console.clear();
        }, 1000);
    }
    antiDebug();
})();
// ===== 反调试保护结束 =====

`;

    // 在 JS 代码开头插入反调试代码
    jsCode = antiDebugCode + jsCode;

    // 6. 混淆代码
    console.log('→ 正在混淆代码...');
    const obfuscationResult = JavaScriptObfuscator.obfuscate(jsCode, {
        // 压缩选项
        compact: true,
        controlFlowFlattening: true,
        controlFlowFlatteningThreshold: 0.75,
        deadCodeInjection: true,
        deadCodeInjectionThreshold: 0.4,
        debugProtection: true,
        debugProtectionInterval: 2000,
        disableConsoleOutput: true,
        identifierNamesGenerator: 'hexadecimal',
        log: false,
        numbersToExpressions: true,
        renameGlobals: false,
        selfDefending: true,
        simplify: true,
        splitStrings: true,
        splitStringsChunkLength: 5,
        stringArray: true,
        stringArrayCallsTransform: true,
        stringArrayEncoding: ['rc4'],
        stringArrayIndexShift: true,
        stringArrayRotate: true,
        stringArrayShuffle: true,
        stringArrayWrappersCount: 5,
        stringArrayWrappersChainedCalls: true,
        stringArrayWrappersParametersMaxCount: 5,
        stringArrayWrappersType: 'function',
        stringArrayThreshold: 0.8,
        transformObjectKeys: true,
        unicodeEscapeSequence: false,
        target: 'browser',
        seed: Math.floor(Math.random() * 1000000)
    });

    const obfuscatedCode = obfuscationResult.getObfuscatedCode();

    // 7. 备份原文件并写入混淆后的代码
    const backupFile = TARGET_FILE + '.backup';
    if (!fs.existsSync(backupFile)) {
        fs.copyFileSync(TARGET_FILE, backupFile);
        console.log(`→ 原文件已备份到: ${backupFile}`);
    }

    fs.writeFileSync(TARGET_FILE, obfuscatedCode, 'utf8');

    // 输出统计
    const originalSize = Buffer.byteLength(jsCode, 'utf8');
    const obfuscatedSize = Buffer.byteLength(obfuscatedCode, 'utf8');
    const ratio = ((obfuscatedSize / originalSize) * 100).toFixed(1);

    console.log('\n✅ 混淆完成！');
    console.log(`→ 原始大小: ${(originalSize / 1024).toFixed(2)} KB`);
    console.log(`→ 混淆大小: ${(obfuscatedSize / 1024).toFixed(2)} KB`);
    console.log(`→ 膨胀比例: ${ratio}%`);
    console.log(`→ 输出文件: ${TARGET_FILE}`);

    if (baseUrl || token) {
        console.log('\n⚠️  注意：API 地址和 Token 已硬编码到混淆后的 JS 中，如需修改请从 .backup 文件恢复后重新运行脚本');
    }

    rl.close();
}

main().catch(err => {
    console.error('发生错误:', err);
    rl.close();
    process.exit(1);
});