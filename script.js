const STORAGE_KEY = 'studyPlannerTasks';

const taskForm = document.getElementById('taskForm');
const subjectInput = document.getElementById('subject');
const taskInput = document.getElementById('task');
const dueDateInput = document.getElementById('dueDate');
const priorityInput = document.getElementById('priority');
const taskList = document.getElementById('taskList');
const todayList = document.getElementById('todayList');
const emptyState = document.getElementById('emptyState');
const clearCompletedBtn = document.getElementById('clearCompleted');
const clearAllBtn = document.getElementById('clearAll');

let tasks = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

function saveTasks() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
}

function updateProgress() {
  const progressBar = document.getElementById('progressBar');
  const progressText = document.getElementById('progressText');
  if (!progressBar || !progressText) return;

  const total = tasks.length;
  if (total === 0) {
    progressBar.style.width = '0%';
    progressText.textContent = 'No tasks yet';
    return;
  }

  const completed = tasks.filter(t => t.completed).length;
  const percent = Math.round((completed / total) * 100);
  progressBar.style.width = `${percent}%`;
  progressText.textContent = `${percent}% done • ${completed} / ${total} complete`;
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function renderTasks() {
  taskList.innerHTML = '';
  todayList.innerHTML = '';

  if (tasks.length === 0) {
    emptyState.style.display = 'block';
    return;
  }

  emptyState.style.display = 'none';

  const todayString = new Date().toISOString().split('T')[0];
  const todayTasks = tasks.filter(t => t.dueDate === todayString && !t.completed);

  todayTasks.forEach(task => {
    const li = document.createElement('li');
    li.textContent = `${task.subject}: ${task.task} (${formatDate(task.dueDate)})`;
    todayList.appendChild(li);
  });

  tasks.sort((a, b) => a.completed - b.completed || new Date(a.dueDate) - new Date(b.dueDate));

  updateProgress();

  tasks.forEach(task => {
    const li = document.createElement('li');
    li.className = 'task' + (task.completed ? ' completed' : '');

    const left = document.createElement('div');
    left.className = 'task-left';

    const title = document.createElement('p');
    title.className = 'task-title';
    title.textContent = `${task.subject} - ${task.task}`;

    const meta = document.createElement('p');
    meta.className = 'task-meta';
    meta.innerHTML = `Due: <strong>${formatDate(task.dueDate)}</strong> · Priority: <span class="priority-${task.priority}">${task.priority}</span>`;

    left.appendChild(title);
    left.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'task-actions';

    const toggle = document.createElement('button');
    toggle.textContent = task.completed ? 'Unmark' : 'Complete';
    toggle.addEventListener('click', () => {
      task.completed = !task.completed;
      saveTasks();
      renderTasks();
    });

    const deleteBtn = document.createElement('button');
    deleteBtn.textContent = 'Delete';
    deleteBtn.addEventListener('click', () => {
      tasks = tasks.filter(t => t.id !== task.id);
      saveTasks();
      renderTasks();
    });

    actions.appendChild(toggle);
    actions.appendChild(deleteBtn);

    li.appendChild(left);
    li.appendChild(actions);
    taskList.appendChild(li);
  });
}

function addTask(e) {
  e.preventDefault();

  const newTask = {
    id: Date.now(),
    subject: subjectInput.value.trim(),
    task: taskInput.value.trim(),
    dueDate: dueDateInput.value,
    priority: priorityInput.value,
    completed: false,
  };

  tasks.push(newTask);
  saveTasks();
  renderTasks();

  taskForm.reset();
  dueDateInput.valueAsDate = new Date();
}

taskForm.addEventListener('submit', addTask);
clearCompletedBtn.addEventListener('click', () => {
  tasks = tasks.filter(t => !t.completed);
  saveTasks();
  renderTasks();
});

clearAllBtn.addEventListener('click', () => {
  if (confirm('Clear all tasks?')) {
    tasks = [];
    saveTasks();
    renderTasks();
  }
});

window.addEventListener('load', () => {
  dueDateInput.valueAsDate = new Date();
  renderTasks();
});
