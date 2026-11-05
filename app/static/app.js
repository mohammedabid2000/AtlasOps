let apiKey = '';
const message = document.querySelector('#message');
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type':'application/json', 'X-API-Key':apiKey}});
  if (!response.ok) throw new Error(`Request failed (${response.status}). Check your key and service readiness.`);
  return response.status === 204 ? null : response.json();
}
async function refresh() {
  const tasks = await api('/api/tasks');
  const list = document.querySelector('#tasks');
  list.replaceChildren();
  document.querySelector('#count').textContent = `${tasks.length} tasks (first 50)`;
  for (const task of tasks) {
    const li = document.createElement('li');
    if (task.done) li.className = 'done';
    const title = document.createElement('span'); title.textContent = task.title;
    const toggle = document.createElement('button'); toggle.textContent = task.done ? 'Reopen' : 'Done';
    toggle.onclick = () => action(async () => {await api(`/api/tasks/${task.id}`, {method:'PATCH',body:JSON.stringify({done:!task.done})}); await refresh();});
    const remove = document.createElement('button'); remove.textContent = 'Delete';
    remove.onclick = () => action(async () => {await api(`/api/tasks/${task.id}`, {method:'DELETE'}); await refresh();});
    li.append(title, toggle, remove); list.append(li);
  }
}
async function action(fn) {try {message.textContent='';await fn();} catch(error) {message.textContent=error.message;}}
document.querySelector('#auth').onsubmit = event => {event.preventDefault(); apiKey=document.querySelector('#key').value;document.querySelector('#key').value='';action(refresh);};
document.querySelector('#add').onsubmit = event => {event.preventDefault();action(async () => {await api('/api/tasks',{method:'POST',body:JSON.stringify({title:document.querySelector('#title').value})});document.querySelector('#title').value='';await refresh();});};
fetch('/health/ready').then(r=>{document.querySelector('#status').textContent=r.ok?'Service ready':'Service not ready';}).catch(()=>{document.querySelector('#status').textContent='Service unavailable';});
