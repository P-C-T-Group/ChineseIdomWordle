/* ============================================================
 * 内置弹窗组件（Dialog / Modal）
 * 提供 Promise-based API，替代浏览器原生 alert / confirm
 *
 * 用法：
 *   // 确认框（返回 true/false）
 *   const ok = await CWDialog.confirm('确定要清空所有历史记录吗？', {
 *     title: '确认操作',
 *     confirmText: '清空',
 *     danger: true
 *   });
 *   if (ok) { ... }
 *
 *   // 提示框（返回 true）
 *   await CWDialog.alert('操作成功', { title: '提示' });
 *
 *   // 自定义按钮
 *   const choice = await CWDialog.show({
 *     title: '游戏结束',
 *     message: '是否重启游戏？',
 *     buttons: [
 *       { text: '取消', value: false },
 *       { text: '重启', value: true, primary: true }
 *     ]
 *   });
 *
 * 兼容性：原生 Promise，无外部依赖；移动端友好；支持 ESC/遮罩关闭。
 * ============================================================ */
(function (global) {
    'use strict';

    const SVG_ICONS = {
        close: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>'
    };

    let openCount = 0; // 当前打开的弹窗数量，用于管理滚动锁定

    /**
     * 创建并显示一个弹窗
     * @param {Object} options 配置项
     * @returns {Promise<any>} 返回用户选择的按钮 value
     */
    function show(options) {
        const opts = Object.assign({
            title: '',           // 标题，空字符串则隐藏标题栏
            message: '',         // 内容（支持 \n 换行、纯文本）
            html: false,         // 是否将 message 作为 HTML 渲染
            buttons: [           // 默认按钮配置
                { text: '取消', value: false },
                { text: '确定', value: true, primary: true }
            ],
            closeOnOverlay: true, // 点击遮罩是否关闭（默认返回 undefined）
            closeOnEsc: true,    // ESC 是否关闭
            showClose: true      // 是否显示右上角关闭按钮
        }, options);

        return new Promise(function (resolve) {
            // —— DOM 构建 ——
            const overlay = document.createElement('div');
            overlay.className = 'cw-overlay';
            overlay.setAttribute('role', 'dialog');
            overlay.setAttribute('aria-modal', 'true');

            const dialog = document.createElement('div');
            dialog.className = 'cw-dialog';

            // 标题栏
            if (opts.title) {
                const header = document.createElement('div');
                header.className = 'cw-dialog__header';

                const title = document.createElement('h3');
                title.className = 'cw-dialog__title';
                title.textContent = opts.title;
                header.appendChild(title);

                if (opts.showClose) {
                    const closeBtn = document.createElement('button');
                    closeBtn.className = 'cw-dialog__close';
                    closeBtn.type = 'button';
                    closeBtn.setAttribute('aria-label', '关闭');
                    closeBtn.innerHTML = SVG_ICONS.close;
                    closeBtn.addEventListener('click', function () {
                        close(undefined);
                    });
                    header.appendChild(closeBtn);
                }
                dialog.appendChild(header);
            }

            // 内容区
            if (opts.message !== '') {
                const body = document.createElement('div');
                body.className = 'cw-dialog__body';
                if (opts.html) {
                    body.innerHTML = opts.message;
                } else {
                    body.textContent = opts.message;
                }
                dialog.appendChild(body);
            }

            // 按钮区
            const footer = document.createElement('div');
            footer.className = 'cw-dialog__footer';
            opts.buttons.forEach(function (btn) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'cw-btn';
                if (btn.primary) button.classList.add('cw-btn--primary');
                if (btn.danger) button.classList.add('cw-btn--danger');
                button.textContent = btn.text;
                button.addEventListener('click', function () {
                    close(btn.value);
                });
                footer.appendChild(button);
            });
            dialog.appendChild(footer);

            overlay.appendChild(dialog);

            // —— 关闭逻辑 ——
            let resolved = false;
            function close(value) {
                if (resolved) return;
                resolved = true;

                overlay.classList.remove('cw-show');
                document.removeEventListener('keydown', onKeydown);

                // 等待过渡动画后移除 DOM
                setTimeout(function () {
                    if (overlay.parentNode) {
                        overlay.parentNode.removeChild(overlay);
                    }
                    openCount = Math.max(0, openCount - 1);
                    if (openCount === 0) {
                        restoreScroll();
                    }
                }, 220);

                resolve(value);
            }

            function onKeydown(e) {
                if (e.key === 'Escape' && opts.closeOnEsc) {
                    e.preventDefault();
                    close(undefined);
                } else if (e.key === 'Enter') {
                    // 回车触发主按钮
                    const primaryBtn = opts.buttons.find(function (b) { return b.primary; });
                    if (primaryBtn) {
                        e.preventDefault();
                        close(primaryBtn.value);
                    }
                }
            }

            // 遮罩点击
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay && opts.closeOnOverlay) {
                    close(undefined);
                }
            });

            // —— 显示 ——
            document.body.appendChild(overlay);
            document.addEventListener('keydown', onKeydown);
            openCount += 1;
            lockScroll();

            // 触发过渡动画
            requestAnimationFrame(function () {
                overlay.classList.add('cw-show');
                // 自动聚焦首个按钮，便于键盘操作
                const firstBtn = footer.querySelector('.cw-btn');
                if (firstBtn) firstBtn.focus();
            });
        });
    }

    /**
     * confirm 风格弹窗
     * @param {string} message 内容
     * @param {Object} [options] 额外配置
     * @returns {Promise<boolean>}
     */
    function confirm(message, options) {
        const opts = Object.assign({
            title: '确认',
            message: message,
            confirmText: '确定',
            cancelText: '取消',
            danger: false
        }, options);

        return show({
            title: opts.title,
            message: opts.message,
            closeOnOverlay: true,
            closeOnEsc: true,
            buttons: [
                { text: opts.cancelText, value: false },
                { text: opts.confirmText, value: true, primary: !opts.danger, danger: opts.danger }
            ]
        }).then(function (v) { return v === true; });
    }

    /**
     * alert 风格弹窗
     * @param {string} message 内容
     * @param {Object} [options] 额外配置
     * @returns {Promise<boolean>}
     */
    function alert(message, options) {
        const opts = Object.assign({
            title: '提示',
            message: message,
            confirmText: '我知道了'
        }, options);

        return show({
            title: opts.title,
            message: opts.message,
            closeOnOverlay: false,
            closeOnEsc: true,
            buttons: [
                { text: opts.confirmText, value: true, primary: true }
            ]
        }).then(function () { return true; });
    }

    // —— 滚动锁定辅助 ——
    let savedOverflow = '';
    function lockScroll() {
        if (savedOverflow === '') {
            savedOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';
        }
    }
    function restoreScroll() {
        document.body.style.overflow = savedOverflow;
        savedOverflow = '';
    }

    global.CWDialog = { show: show, confirm: confirm, alert: alert };
})(typeof window !== 'undefined' ? window : this);
