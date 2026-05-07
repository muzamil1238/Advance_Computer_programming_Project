function $(sel, root = document) {
	return root.querySelector(sel);
}

function $all(sel, root = document) {
	return Array.from(root.querySelectorAll(sel));
}

function showToast(message) {
	const el = $('#toast');
	if (!el) return;
	el.textContent = message;
	el.classList.remove('hidden');
	clearTimeout(window.__toastTimer);
	window.__toastTimer = setTimeout(() => el.classList.add('hidden'), 2600);
}

function openModal(id) {
	const el = document.getElementById(id);
	if (!el) return;
	el.classList.remove('hidden');
	el.classList.add('flex');
}

function closeModal(id) {
	const el = document.getElementById(id);
	if (!el) return;
	el.classList.add('hidden');
	el.classList.remove('flex');
}

async function apiCheckin({ habitId, completed, notes, dateStr }) {
	const res = await fetch('/api/checkin', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ habit_id: habitId, completed, notes, date: dateStr }),
	});
	const data = await res.json();
	if (!data.ok) throw new Error('Request failed');
	return data;
}

function initNavAndReminders() {
	const mobileBtn = $('#mobileMenuBtn');
	const mobileNav = $('#mobileNav');
	if (mobileBtn && mobileNav) {
		mobileBtn.addEventListener('click', () => {
			mobileNav.classList.toggle('hidden');
		});
	}

	const reminderBtn = $('#reminderBtn');
	const reminderMenu = $('#reminderMenu');
	if (reminderBtn && reminderMenu) {
		reminderBtn.addEventListener('click', (e) => {
			e.stopPropagation();
			reminderMenu.classList.toggle('hidden');
		});

		document.addEventListener('click', () => reminderMenu.classList.add('hidden'));
		$all('.reminderItem', reminderMenu).forEach((btn) => {
			btn.addEventListener('click', (e) => {
				e.preventDefault();
				const msg = btn.getAttribute('data-msg') || 'Reminder';
				showToast(msg);
				reminderMenu.classList.add('hidden');
			});
		});
	}
}

function initModals() {
	$all('.js-open-modal').forEach((btn) => {
		btn.addEventListener('click', () => openModal(btn.getAttribute('data-modal')));
	});
	$all('.js-close-modal').forEach((btn) => {
		btn.addEventListener('click', () => closeModal(btn.getAttribute('data-modal')));
	});

	// Close modal when clicking backdrop
	$all('[id$="Modal"]').forEach((modal) => {
		modal.addEventListener('click', (e) => {
			if (e.target === modal) {
				modal.classList.add('hidden');
				modal.classList.remove('flex');
			}
		});
	});
}

function initDashboardInteractions() {
	const kpiStreak = $('#kpiStreak');
	const kpiSuccess = $('#kpiSuccessRate');

	// Edit habit modal wiring
	const editForm = $('#editHabitForm');
	const editName = $('#editHabitName');
	const editCategory = $('#editHabitCategory');
	const editTarget = $('#editHabitTarget');
	$all('.js-edit-habit').forEach((btn) => {
		btn.addEventListener('click', () => {
			const id = btn.getAttribute('data-habit-id');
			if (!id || !editForm) return;
			editForm.action = `/habits/${id}`;
			if (editName) editName.value = btn.getAttribute('data-name') || '';
			if (editCategory) editCategory.value = btn.getAttribute('data-category') || 'Other';
			if (editTarget) editTarget.value = btn.getAttribute('data-target') || '7';
			openModal('editHabitModal');
		});
	});

	// Check-ins (checkbox + notes)
	$all('.js-checkin').forEach((checkbox) => {
		checkbox.addEventListener('change', async () => {
			const habitId = Number(checkbox.getAttribute('data-habit-id'));
			const card = checkbox.closest('[data-habit-card]');
			const notesEl = card ? $('.js-notes', card) : null;
			const notes = notesEl ? notesEl.value : '';

			checkbox.disabled = true;
			try {
				const data = await apiCheckin({ habitId, completed: checkbox.checked, notes, dateStr: new Date().toISOString().slice(0, 10) });
				if (kpiStreak) kpiStreak.textContent = String(data.streak);
				if (kpiSuccess) kpiSuccess.textContent = String(data.success_rate);
				showToast(checkbox.checked ? 'Saved: completed ✅' : 'Saved: unchecked');
			} catch (e) {
				checkbox.checked = !checkbox.checked;
				showToast('Could not save. Try again.');
			} finally {
				checkbox.disabled = false;
			}
		});
	});

	$all('.js-notes').forEach((textarea) => {
		textarea.addEventListener('blur', async () => {
			const habitId = Number(textarea.getAttribute('data-habit-id'));
			const card = textarea.closest('[data-habit-card]');
			const checkbox = card ? $('.js-checkin', card) : null;
			const completed = checkbox ? checkbox.checked : false;

			textarea.disabled = true;
			try {
				const data = await apiCheckin({ habitId, completed, notes: textarea.value, dateStr: new Date().toISOString().slice(0, 10) });
				if (kpiStreak) kpiStreak.textContent = String(data.streak);
				if (kpiSuccess) kpiSuccess.textContent = String(data.success_rate);
				showToast('Notes saved');
			} catch (e) {
				showToast('Could not save notes');
			} finally {
				textarea.disabled = false;
			}
		});
	});
}

document.addEventListener('DOMContentLoaded', () => {
	initNavAndReminders();
	initModals();
	initDashboardInteractions();
});