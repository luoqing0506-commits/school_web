// 无错语言 VSCode 扩展激活入口
// 当前版本：语法高亮 + 代码片段补全（纯声明式，无需运行时代码）
// 未来：可加运行/检查/REPL 集成

const vscode = require('vscode');

function activate(context) {
    // 首次打开 .wc 文件时提示一下
    context.subscriptions.push(
        vscode.commands.registerCommand('wucuo.hello', () => {
            vscode.window.showInformationMessage(
                '无错语言 WucuoLang：把"怎么写"交给语法，把"写什么"还给人脑。'
            );
        })
    );
    console.log('无错语言扩展已激活');
}

function deactivate() {}

module.exports = { activate, deactivate };
