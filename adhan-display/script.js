// —— CONFIG ——
const latitude  = 40.207527;   // your latitude
const longitude =  -74.829727;  // your longitude
const method    = 'ISNA';    // calculation method
// ——————————

const pt = new PrayTimes(method);
// override ISNA’s default 15° fajr angle to 18°
pt.adjust({ fajr: 18 });

function pad(n) { return (n<10?'0':'')+n; }

// this updates the countdown text once
function updateCountdown(target) {
  const diff = target - new Date();
  if (diff <= 0) {
    renderTimes(); // we've arrived; refresh everything
    return;
  }
  const h = Math.floor(diff/3600000);
  const m = Math.floor((diff%3600000)/60000);
  const s = Math.floor((diff%60000)/1000);
  document.getElementById('countdown')
          .textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
}

// starts (or restarts) the repeating countdown
let countdownInterval;
function startCountdown(target) {
  clearInterval(countdownInterval);
  updateCountdown(target);                       // **immediate** update
  countdownInterval = setInterval(() => {
    updateCountdown(target);
  }, 500);
}

function renderTimes() {
  const now = new Date();
  document.getElementById('date').textContent =
    now.toLocaleDateString(undefined, {
      weekday:'long', month:'long', day:'numeric'
    });

  const times = pt.getTimes(now, [latitude, longitude]);
  const names = ['fajr','sunrise','dhuhr','asr','maghrib','isha'];

  // render the list
  const ul = document.getElementById('times');
  ul.innerHTML = '';
  names.forEach(name => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="name">
        ${name.charAt(0).toUpperCase()+name.slice(1)}
      </span>
      <span class="time">${times[name]}</span>
    `;
    ul.appendChild(li);
  });

  // build upcoming array for *today*
  let upcoming = names
    .map(n => {
      const [h,m] = times[n].split(':').map(Number);
      const dt = new Date(now);
      dt.setHours(h, m, 0);
      return { name:n, time:dt };
    })
    .filter(o => o.time > now)
    .sort((a,b) => a.time - b.time);

  // if none left today, schedule tomorrow's fajr
  if (!upcoming.length) {
    const tomorrow = new Date(now);
    tomorrow.setDate(now.getDate()+1);
    const tomTimes = pt.getTimes(tomorrow, [latitude, longitude]);
    const [h,m] = tomTimes.fajr.split(':').map(Number);
    const fajrTime = new Date(now);
    fajrTime.setDate(now.getDate()+1);
    fajrTime.setHours(h, m, 0);
    upcoming = [{ name:'fajr', time:fajrTime }];
  }

  // whatever the first in upcoming is, use that
  const next = upcoming[0];
  document.getElementById('nextName').textContent =
    next.name.charAt(0).toUpperCase() + next.name.slice(1);
  startCountdown(next.time);
}

// initial paint + recalc every minute (to catch midnight rollover)
renderTimes();
setInterval(renderTimes, 60*10000);
