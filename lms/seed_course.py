# Generic course builder: turns authored content JSON into a full LMS course.
# Content dir (docker cp'd) must hold: course.json, ch*.json, meta.json, images/.
#
#   bench --site new-money.42bucks.com execute lms.seed_course.run --kwargs "{'content_dir': '/tmp/nmu-vibe'}"
#
# course.json: {"title", "name" (optional fixed docname), "category", "tags",
#               "intro", "description", "cover" (image slug), "instructor"}
# Rebuilds chapters/lessons in place, keeping the course doc, its enrollments
# and rating. Idempotent per-object; images are re-uploaded when they change.

import json
import os

import frappe

DEFAULT_INSTRUCTOR = "dean@new-money.42bucks.com"


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
		elif t == "divider":
			# The markdown tool writes `text` straight into innerHTML, so emit
			# the rule as HTML - "---" would render as three literal dashes.
			out.append({"id": block_id(), "type": "markdown", "data": {"text": "<hr>"}})
	return json.dumps({"time": 1754812800000, "blocks": out, "version": "2.29.0"}, ensure_ascii=False)


def upload_images(images_dir, course_name, prefix):
	from frappe.utils.file_manager import save_file

	urls = {}
	if not os.path.isdir(images_dir):
		return urls
	for fname in sorted(os.listdir(images_dir)):
		if not fname.endswith(".png"):
			continue
		slug = fname[:-4]
		with open(os.path.join(images_dir, fname), "rb") as f:
			payload = f.read()
		existing = frappe.get_all(
			"File",
			{"attached_to_doctype": "LMS Course", "attached_to_name": course_name,
			 "file_name": ["like", f"{prefix}-{slug}%"]},
			["name", "file_url", "file_size"],
		)
		fresh = next((f for f in existing if f.file_size == len(payload)), None)
		if fresh:
			urls[slug] = fresh.file_url
			continue
		for stale in existing:
			frappe.delete_doc("File", stale.name, force=1, ignore_permissions=True)
		doc = save_file(f"{prefix}-{slug}.png", payload, "LMS Course", course_name, is_private=0)
		urls[slug] = doc.file_url
	return urls


def ensure_quizzes(meta):
	names = {}
	for slug, spec in meta.get("quizzes", {}).items():
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


def ensure_assignments(meta, course_name):
	names = {}
	for slug, spec in meta.get("assignments", {}).items():
		existing = frappe.db.exists("LMS Assignment", {"title": spec["title"]})
		if existing:
			names[slug] = existing
			continue
		doc = frappe.new_doc("LMS Assignment")
		doc.title = spec["title"]
		doc.type = spec.get("type", "Text")
		doc.question = spec["question"]
		doc.course = course_name
		doc.save()
		names[slug] = doc.name
	return names


def wipe_lessons(course):
	for lesson in frappe.get_all("Course Lesson", {"course": course.name}, pluck="name"):
		frappe.db.delete("LMS Course Progress", {"lesson": lesson})
		frappe.delete_doc("Course Lesson", lesson, force=1)
	for chapter in frappe.get_all("Course Chapter", {"course": course.name}, pluck="name"):
		frappe.delete_doc("Course Chapter", chapter, force=1)
	course.reload()
	course.set("chapters", [])
	course.save()


def ensure_course(spec):
	existing = spec.get("name") and frappe.db.exists("LMS Course", spec["name"])
	if not existing:
		existing = frappe.db.exists("LMS Course", {"title": spec["title"]})
	if existing:
		course = frappe.get_doc("LMS Course", existing)
	else:
		category = spec.get("category", "Заработок")
		if category and not frappe.db.exists("LMS Category", category):
			frappe.get_doc({"doctype": "LMS Category", "category": category}).insert()
		course = frappe.new_doc("LMS Course")
		if spec.get("name"):
			course.name = spec["name"]
		course.update({
			"title": spec["title"],
			"category": category,
			"published": 1,
			"published_on": frappe.utils.now(),
			"instructors": [{"instructor": spec.get("instructor", DEFAULT_INSTRUCTOR)}],
		})
		course.insert()
	course.title = spec["title"]
	course.short_introduction = spec["intro"]
	course.description = spec["description"]
	course.tags = spec.get("tags", "")
	course.published = 1
	course.save()
	return course


def run(content_dir):
	spec = json.load(open(os.path.join(content_dir, "course.json")))
	meta = json.load(open(os.path.join(content_dir, "meta.json")))
	course = ensure_course(spec)

	prefix = spec.get("image_prefix", "img")
	image_urls = upload_images(os.path.join(content_dir, "images"), course.name, prefix)
	quiz_names = ensure_quizzes(meta)
	assignment_names = ensure_assignments(meta, course.name)

	wipe_lessons(course)

	if spec.get("cover") and image_urls.get(spec["cover"]):
		course.reload()
		course.image = image_urls[spec["cover"]]
		course.save()

	chapter_files = sorted(f for f in os.listdir(content_dir) if f.startswith("ch") and f.endswith(".json"))
	lessons = 0
	for fname in chapter_files:
		data = json.load(open(os.path.join(content_dir, fname)))
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
			lesson.content = to_editorjs(lesson_spec["blocks"], image_urls, quiz_names, assignment_names)
			lesson.save()
			chapter.reload()
			chapter.append("lessons", {"lesson": lesson.name})
			chapter.save()
			lessons += 1

	frappe.db.commit()
	print("Course:", course.name, "|", course.title)
	print("  chapters:", len(chapter_files))
	print("  lessons:", lessons)
	print("  images:", len(image_urls))
	print("  quizzes:", len(quiz_names), "assignments:", len(assignment_names))
