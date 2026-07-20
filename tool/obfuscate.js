#!/usr/bin/env node

/**
 * 成语Wordle 前端 JS 混淆脚本
 * 功能：
 * 1. 替换 API baseURL 和 token
 * 2. 添加反调试代码
 * 3. 混淆 JS 代码（支持多个文件）
 * 4. 输出替换原文件
 * 
 * 支持的文件：
 * - client/js/indexScript.js (主游戏)
 * - client/js/top.js (排行榜)
 * - client/js/dialog.js (弹窗组件)
 * - client/js/help.js (帮助页)
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const crypto = require('crypto');

const JavaScriptObfuscator = require('javascript-obfuscator');

// 目标文件列表（相对于项目根目录）
const TARGET_FILES = [
    'client/js/indexScript.js',
    'client/js/top.js',
    'client/js/dialog.js',
    'client/js/help.js'
];

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

// 处理单个文件
function processFile(filePath, baseUrl, token, antiDebugEnabled) {
    const defaultBaseUrl = '127.0.0.1:8000';
    const defaultToken = 'test-token';
    
    console.log(`\n处理文件: ${filePath}`);
    
    // 1. 读取原始 JS 文件
    if (!fs.existsSync(filePath)) {
        console.log(`  ⚠️  文件不存在，跳过: ${filePath}`);
        return { success: false, skipped: true };
    }

    let jsCode = fs.readFileSync(filePath, 'utf8');
    const originalSize = Buffer.byteLength(jsCode, 'utf8');

    // 2. 检查文件是否已经被混淆（简单检测）
    if (jsCode.includes('===== 反调试保护 =====') && antiDebugEnabled) {
        console.log('  ⚠️  文件似乎已包含反调试代码');
    }

    // 3. 替换 baseURL
    let actualBaseUrl = defaultBaseUrl;
    if (baseUrl) {
        let processedBaseUrl = baseUrl.trim();
        processedBaseUrl = processedBaseUrl.replace(/^https?:\/\//i, '');
        processedBaseUrl = processedBaseUrl.replace(/\/+$/, '');
        actualBaseUrl = processedBaseUrl;

        jsCode = jsCode.split(`//${defaultBaseUrl}`).join(`//${processedBaseUrl}`);
        jsCode = jsCode.split(`http://${defaultBaseUrl}`).join(`http://${processedBaseUrl}`);
        jsCode = jsCode.split(`https://${defaultBaseUrl}`).join(`https://${processedBaseUrl}`);
        console.log(`  → API 地址: ${defaultBaseUrl} → ${actualBaseUrl}`);
    } else {
        console.log(`  → 保持默认 API 地址: ${defaultBaseUrl}`);
    }

    // 4. 替换 token
    const actualToken = token || defaultToken;
    const bearerPattern = /'Bearer ([^']+)'/g;
    const matches = jsCode.match(bearerPattern) || [];
    
    if (matches.length > 0) {
        jsCode = jsCode.replace(bearerPattern, `'Bearer ${actualToken}'`);
        console.log(`  → Token 替换: 找到 ${matches.length} 处，${token ? '已替换' : '保持默认'}`);
    } else {
        console.log(`  → 未找到 Bearer Token 配置，跳过替换`);
    }

    // 5. 添加反调试代码
    if (antiDebugEnabled) {
        const antiDebugCode = `
// ===== 反调试保护 =====
(function() {
    function antiDebug() {
        const startTime = new Date();
        debugger;
        const endTime = new Date();
        if (endTime - startTime > 100) {
            document.body.innerHTML = '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:99999;font-family:sans-serif;"><h1 style="color:var(--primary);font-size:2em;margin-bottom:1rem;">检测到开发者工具</h1><p style="color:var(--text-secondary);">请关闭开发者工具后刷新页面</p></div>';
            return;
        }
        setInterval(function() {
            const start = performance.now();
            debugger;
            const end = performance.now();
            if (end - start > 100) {
                document.body.innerHTML = '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;z-index:99999;font-family:sans-serif;"><h1 style="color:var(--primary);font-size:2em;margin-bottom:1rem;">检测到调试器</h1><p style="color:var(--text-secondary);">请关闭调试工具后刷新页面</p></div>';
            }
        }, 1000);
        document.addEventListener('contextmenu', function(e) { e.preventDefault(); return false; });
        document.addEventListener('keydown', function(e) {
            if (e.key === 'F12') { e.preventDefault(); return false; }
            if (e.ctrlKey && e.shiftKey && ['I', 'J', 'C'].includes(e.key.toUpperCase())) { e.preventDefault(); return false; }
            if (e.ctrlKey && e.key.toUpperCase() === 'U') { e.preventDefault(); return false; }
        });
        console.log = function() {}; console.warn = function() {}; console.info = function() {}; console.error = function() {};
        setInterval(function() { console.clear(); }, 1000);
    }
    antiDebug();
})();
// ===== 反调试保护结束 =====

`;
        jsCode = antiDebugCode + jsCode;
        console.log('  → 已添加反调试保护');
    }

    // 6. 混淆代码
    console.log('  → 正在混淆代码...');
    const obfuscationResult = JavaScriptObfuscator.obfuscate(jsCode, {
        compact: true,
        simplify: true,
        identifierNamesGenerator: 'hexadecimal',
        renameGlobals: false,
        selfDefending: true,
        debugProtection: true,
        debugProtectionInterval: 8000,
        disableConsoleOutput: true,
        controlFlowFlattening: false,
        deadCodeInjection: false,
        numbersToExpressions: false,
        splitStrings: false,
        transformObjectKeys: false,
        unicodeEscapeSequence: false,
        stringArray: true,
        stringArrayEncoding: [],
        stringArrayWrappersCount: 1,
        stringArrayThreshold: 0.3,
        stringArrayRotate: true,
        stringArrayShuffle: true,
        target: 'browser',
        seed: Math.floor(Math.random() * 1000000)
    });

    const obfuscatedCode = obfuscationResult.getObfuscatedCode();

    // 7. 备份原文件并写入
    const backupFile = filePath + '.backup';
    if (!fs.existsSync(backupFile)) {
        fs.copyFileSync(filePath, backupFile);
        console.log(`  → 原文件已备份到: ${backupFile}`);
    } else {
        console.log(`  → 备份文件已存在: ${backupFile}`);
    }

    fs.writeFileSync(filePath, obfuscatedCode, 'utf8');

    const obfuscatedSize = Buffer.byteLength(obfuscatedCode, 'utf8');
    const ratio = ((obfuscatedSize / originalSize) * 100).toFixed(1);
    console.log(`  ✅ 完成: ${(originalSize / 1024).toFixed(2)} KB → ${(obfuscatedSize / 1024).toFixed(2)} KB (${ratio}%)`);
    
    return { success: true, originalSize, obfuscatedSize, ratio };
}

async function main() {
    console.log('=== 成语Wordle JS 混淆工具 ===\n');
    console.log(`将处理以下 ${TARGET_FILES.length} 个文件:`);
    TARGET_FILES.forEach(f => console.log(`  - ${f}`));
    console.log('');

    console.log('--- 配置参数 ---');
    const baseUrl = await question('请输入 API Base URL（不含 /api，直接回车保持默认 127.0.0.1:8000）: ');
    const token = await question('请输入 API Token（直接回车保持默认 test-token）: ');
    const antiDebugInput = await question('启用反调试保护？(Y/n，默认启用): ');
    const antiDebugEnabled = !antiDebugInput || antiDebugInput.toLowerCase().startsWith('y');

    console.log('\n--- 开始处理 ---\n');

    const projectRoot = path.join(__dirname, '..');
    const results = [];
    let totalOriginalSize = 0;
    let totalObfuscatedSize = 0;

    for (const relPath of TARGET_FILES) {
        const fullPath = path.join(projectRoot, relPath);
        const result = processFile(fullPath, baseUrl, token, antiDebugEnabled);
        if (result.success) {
            totalOriginalSize += result.originalSize;
            totalObfuscatedSize += result.obfuscatedSize;
        }
        results.push({ file: relPath, ...result });
    }

    console.log('\n--- 处理完成 ---');
    console.log(`成功处理: ${results.filter(r => r.success).length} / ${TARGET_FILES.length} 个文件`);
    console.log(`总原始大小: ${(totalOriginalSize / 1024).toFixed(2)} KB`);
    console.log(`总混淆大小: ${(totalObfuscatedSize / 1024).toFixed(2)} KB`);
    console.log(`总膨胀比例: ${((totalObfuscatedSize / totalOriginalSize) * 100).toFixed(1)}%`);

    console.log('\n⚠️  重要说明：');
    console.log('  - API 地址和 Token 已硬编码到混淆后的 JS 中');
    console.log('  - 如需修改配置，请从 .backup 文件恢复原始文件后重新运行本脚本');
    console.log('  - 原始备份文件位置: <文件名>.backup');

    console.log('\n📝 恢复原始文件方法：');
    console.log('  方法1: 使用 git checkout 恢复: git checkout client/js/*.js');
    console.log('  方法2: 手动将 .backup 文件重命名去掉 .backup 后缀');

    const actualToken = token || 'test-token';
    const tokenHash = crypto.createHash('sha256').update(actualToken).digest('hex');
    console.log(`\n🔑 当前前端 Token: ${actualToken}`);
    console.log(`   SHA256 哈希: ${tokenHash}`);
    console.log('   请通过 /api/admin/tokens/add 接口将此Token添加到后端数据库');

    rl.close();
}

main().catch(err => {
    console.error('\n❌ 发生错误:', err);
    rl.close();
    process.exit(1);
});
