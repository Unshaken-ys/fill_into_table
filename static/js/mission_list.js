// 任务清单页：输入任务 → 回车 / 点「添加」→ 追加到列表
// 脚本在 body 末尾加载，这里三个元素一定已经存在
const literalField = document.querySelector('.literal_field');
const list = document.querySelector('.list');
const button = document.getElementById('input1');

function newMission() {
    const text = literalField.value.trim();
    if (!text) {
        return;
    }

    const mission = document.createElement('li');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'check_block';

    // 用 textContent 而不是拼 innerHTML，任务名里的 < > 才不会被当成标签
    const label = document.createElement('label');
    label.textContent = text;

    const rubbishBin = document.createElement('button');
    rubbishBin.type = 'button';
    rubbishBin.className = 'rubbish_bin';
    rubbishBin.textContent = '🗑️';
    rubbishBin.addEventListener('click', function () {
        mission.remove();
    });

    mission.append(checkbox, label, rubbishBin);
    list.append(mission);

    // 清空输入框，方便连着录下一条
    literalField.value = '';
    literalField.focus();
}

// 事件触发：回车
literalField.addEventListener('keyup', function (e) {
    if (e.key === 'Enter') {
        newMission();
    }
});

// 事件触发：点击「添加」按钮
button.addEventListener('click', newMission);
