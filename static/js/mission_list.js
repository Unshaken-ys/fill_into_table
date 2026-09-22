// 提取页面所有任务
function getMissionList() {
    const arr = [];
    document.querySelectorAll('.list > li').forEach(li => {
        const ck = li.querySelector('.check_block');
        const label = li.querySelector('label');
        arr.push({
            text: label.textContent,
            checked: ck.checked
        })
    })
    return arr;
}
//传到后端：整份清单发过去，后端先删后插做全量替换
async function uploadMission() {
    try {
        const resp = await fetch("/student/mission_list", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ missions: getMissionList() })
        });
        const result = await resp.json();
        console.log("后端返回", result);
    } catch (e) {
        // 未登录会被重定向到登录页，拿到的不是 JSON，这里兜一下
        console.log("保存失败", e);
    }
}

// 任务清单页：输入任务 → 回车 / 点「添加」→ 追加到列表
// 脚本在 body 末尾加载，下面三个元素一定已经存在
const literalField = document.querySelector('.literal_field');
const list = document.querySelector('.list');
const button = document.getElementById('input1');

// 每条任务的 checkbox 都要有个唯一 id，label 才能用 htmlFor 关联上
let missionSeq = 0;

// 造一条任务并追加到列表末尾（新增和回显都走这里）
function addMission(text, checked) {
    const mission = document.createElement('li');

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'check_block';
    checkbox.id = 'mission-' + missionSeq++;
    checkbox.checked = !!checked;

    // 用 textContent 而不是拼 innerHTML，任务名里的 < > 才不会被当成标签
    const label = document.createElement('label');
    label.htmlFor = checkbox.id;
    label.textContent = text;

    // 垃圾桶
    const rubbishBin = document.createElement('button');
    rubbishBin.type = 'button';
    rubbishBin.className = 'rubbish_bin';
    rubbishBin.textContent = '🗑️';

    // 勾完的沉到列表底部：初始渲染时同一条规则
    mission.classList.toggle('done', !!checked);
    mission.append(checkbox, label, rubbishBin);
    if (checked) {
        list.append(mission);
    } else {
        list.prepend(mission);
    }
}

// 回显：后端把已存的任务放在 ul 的 data-tasks 上，倒着插才能保持原顺序
JSON.parse(list.dataset.tasks || '[]').reverse().forEach(t => addMission(t.text, t.checked));

// 输入框取内容 → 造一条 → 存库
function newMission() {
    const text = literalField.value.trim();
    if (!text) {
        return;
    }

    addMission(text, false);
    uploadMission();

    // 清空输入框，方便连着录下一条
    literalField.value = '';
    literalField.focus();
}

// 勾选 / 取消勾选：加 done 类（样式在 mission_list.css），勾完的沉到列表底部
// 用事件委托挂在 .list 上，不给每条任务单独绑监听——任务被删掉时
// 单独绑的监听器会跟着节点一起回收，很容易漏掉
list.addEventListener('change', function (e) {
    if (!e.target.classList.contains('check_block')) {
        return;
    }
    const checkbox = e.target;
    const mission = checkbox.closest('li');
    mission.classList.toggle('done', checkbox.checked);
    if (checkbox.checked) {
        list.append(mission);
    } else {
        list.prepend(mission);
    }
    uploadMission();
});

// 点垃圾桶：删掉整条任务
list.addEventListener('click', function (e) {
    if (e.target.classList.contains('rubbish_bin')) {
        e.target.closest('li').remove();
        uploadMission();
    }
});

// 事件触发：回车
literalField.addEventListener('keyup', function (e) {
    if (e.key === 'Enter') {
        newMission();
    }
});

// 事件触发：点击「添加」按钮
button.addEventListener('click', newMission);
