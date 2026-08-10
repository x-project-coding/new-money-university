# Build the flagship «Лидогенерация» course from authored content JSON.
# Content dir (docker cp'd): /tmp/nmu-leadgen/{ch01..ch10}.json + meta.json
# Images dir:                /tmp/nmu-leadgen/images/<slug>.png
# Replaces the existing stub lessons of course COURSE_NAME in place (keeps the
# course doc, its enrollments and rating). Idempotent per-object.
#   bench --site new-money.42bucks.com execute lms.seed_leadgen.run

import json
import os

import frappe

CONTENT_DIR = "/tmp/nmu-leadgen"
IMAGES_DIR = os.path.join(CONTENT_DIR, "images")
COURSE_NAME = "7qtp1ndple"

COURSE_INTRO = "Полная система: от портрета клиента до подтверждённых лидов - руками и с ИИ-сотрудником."
COURSE_DESCRIPTION = (
	"<p>Большой практический курс о том, как находить клиентов. Вся воронка: портрет клиента и оффер, "
	"сбор и чистка базы, первые сообщения, каналы - email, LinkedIn и WhatsApp для мира, Telegram для России, - "
	"работа с ответами, квалификация лидов и ИИ-автопилот.</p>"
	"<p>Курс построен на практике настоящего агентства лидогенерации и на инструментах платформы: "
	"ИИ-сотруднике и Outreach-приложении, доступ к которым есть у каждого студента. "
	"В каждой главе - словарик для новичков, примеры, квизы и настоящие задания.</p>"
)


def block_id():
	return frappe.generate_hash(length=10)


def to_editorjs(blocks, image_urls, quiz_names, assignment_names):
	out = []
	for b in blocks:
		t = b["t"]
		if t == "p":
			out.append({"id": block_id(), "type": "paragraph", "data": {"text": b["text"]}})
		elif t == "h":
			out.append({"id": block_id(), "type": "header", "data": {"text": b["text"], "level": b.get("level", 3)}})
		elif t == "list":
			items = [{"content": i, "items": []} for i in b["items"]]
			out.append({"id": block_id(), "type": "list", "data": {"style": b.get("style", "unordered"), "items": items}})
		elif t == "table":
			out.append({"id": block_id(), "type": "table", "data": {"withHeadings": bool(b.get("headings")), "content": b["rows"]}})
		elif t == "img":
			url = image_urls.get(b["slug"])
			if url:
				out.append({"id": block_id(), "type": "image", "data": {
					"url": url, "caption": b.get("caption", ""),
					"withBorder": False, "withBackground": False, "stretched": True,
				}})
		elif t == "quiz":
			name = quiz_names.get(b["slug"])
			if name:
				out.append({"id": block_id(), "type": "quiz", "data": {"quiz": name}})
		elif t == "assignment":
			name = assignment_names.get(b["slug"])
			if name:
				out.append({"id": block_id(), "type": "assignment", "data": {"assignment": name}})
		elif t == "code":
			out.append({"id": block_id(), "type": "codeBox", "data": {"code": b["text"]}})
	return json.dumps({"time": 1754812800000, "blocks": out, "version": "2.29.0"}, ensure_ascii=False)


def upload_images():
	from frappe.utils.file_manager import save_file

	urls = {}
	if not os.path.isdir(IMAGES_DIR):
		return urls
	for fname in sorted(os.listdir(IMAGES_DIR)):
		if not fname.endswith(".png"):
			continue
		slug = fname[:-4]
		existing = frappe.db.get_value(
			"File", {"attached_to_doctype": "LMS Course", "attached_to_name": COURSE_NAME,
			         "file_name": ["like", f"lg-{slug}%"]}, "file_url")
		if existing:
			urls[slug] = existing
			continue
		with open(os.path.join(IMAGES_DIR, fname), "rb") as f:
			doc = save_file(f"lg-{slug}.png", f.read(), "LMS Course", COURSE_NAME, is_private=0)
		urls[slug] = doc.file_url
	return urls


def ensure_quizzes(meta):
	names = {}
	for slug, spec in meta["quizzes"].items():
		existing = frappe.db.exists("LMS Quiz", {"title": spec["title"]})
		if existing:
			names[slug] = existing
			continue
		questions = []
		for qspec in spec["questions"]:
			qname = frappe.db.exists("LMS Question", {"question": qspec["q"]})
			if qname:
				questions.append(qname)
				continue
			doc = frappe.new_doc("LMS Question")
			doc.question = qspec["q"]
			doc.type = "Choices"
			doc.multiple = 0
			for i, (text, correct) in enumerate(qspec["options"], start=1):
				setattr(doc, f"option_{i}", text)
				setattr(doc, f"is_correct_{i}", 1 if correct else 0)
			doc.save()
			questions.append(doc.name)
		quiz = frappe.new_doc("LMS Quiz")
		quiz.title = spec["title"]
		quiz.passing_percentage = spec.get("passing_percentage", 70)
		quiz.total_marks = 5 * len(questions)
		for qname in questions:
			quiz.append("questions", {"question": qname, "marks": 5})
		quiz.save()
		names[slug] = quiz.name
	return names


def ensure_assignments(meta):
	names = {}
	for slug, spec in meta["assignments"].items():
		existing = frappe.db.exists("LMS Assignment", {"title": spec["title"]})
		if existing:
			names[slug] = existing
			continue
		doc = frappe.new_doc("LMS Assignment")
		doc.title = spec["title"]
		doc.type = spec.get("type", "Text")
		doc.question = spec["question"]
		doc.course = COURSE_NAME
		doc.save()
		names[slug] = doc.name
	return names


def wipe_existing_lessons(course):
	lessons = frappe.get_all("Course Lesson", {"course": course.name}, pluck="name")
	for lesson in lessons:
		frappe.db.delete("LMS Course Progress", {"lesson": lesson})
		frappe.delete_doc("Course Lesson", lesson, force=1)
	chapters = frappe.get_all("Course Chapter", {"course": course.name}, pluck="name")
	for chapter in chapters:
		frappe.delete_doc("Course Chapter", chapter, force=1)
	course.reload()
	course.set("chapters", [])
	course.save()


def run():
	meta = json.load(open(os.path.join(CONTENT_DIR, "meta.json")))
	course = frappe.get_doc("LMS Course", COURSE_NAME)

	image_urls = upload_images()
	quiz_names = ensure_quizzes(meta)
	assignment_names = ensure_assignments(meta)

	wipe_existing_lessons(course)

	course.title = meta.get("course_title", course.title)
	course.short_introduction = COURSE_INTRO
	course.description = COURSE_DESCRIPTION
	course.save()

	chapter_files = sorted(
		f for f in os.listdir(CONTENT_DIR) if f.startswith("ch") and f.endswith(".json")
	)
	lesson_count = 0
	for fname in chapter_files:
		data = json.load(open(os.path.join(CONTENT_DIR, fname)))
		chapter = frappe.new_doc("Course Chapter")
		chapter.course = course.name
		chapter.title = data["chapter"]
		chapter.save()
		course.reload()
		course.append("chapters", {"chapter": chapter.name})
		course.save()
		for lesson_spec in data["lessons"]:
			lesson = frappe.new_doc("Course Lesson")
			lesson.course = course.name
			lesson.chapter = chapter.name
			lesson.title = lesson_spec["title"]
			lesson.content = to_editorjs(
				lesson_spec["blocks"], image_urls, quiz_names, assignment_names
			)
			lesson.save()
			chapter.reload()
			chapter.append("lessons", {"lesson": lesson.name})
			chapter.save()
			lesson_count += 1

	frappe.db.commit()
	print("Course rebuilt:")
	print("  chapters:", len(chapter_files))
	print("  lessons:", lesson_count)
	print("  images:", len(image_urls))
	print("  quizzes:", list(quiz_names.values()))
	print("  assignments:", len(assignment_names))
