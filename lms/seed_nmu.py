# Seed New Money University: branding settings, signup, outgoing email,
# example courses. Idempotent. Ships with the app so it can run via:
#   bench --site new-money.42bucks.com execute lms.seed_nmu.run
# Reads RESEND_API_KEY from the environment if set (outgoing SMTP via Resend).

import json
import os

import frappe


def block(kind, **data):
	return {"id": frappe.generate_hash(length=10), "type": kind, "data": data}


def content(*blocks):
	return json.dumps({"time": 1754812800000, "blocks": list(blocks), "version": "2.29.0"})


def para(text):
	return block("paragraph", text=text)


def head(text, level=3):
	return block("header", text=text, level=level)


def ensure_user(email, first_name, last_name, roles=()):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"send_welcome_email": 0,
			}
		)
		user.insert(ignore_permissions=True)
	if roles:
		user.add_roles(*roles)
	return user


def ensure_category(name):
	if not frappe.db.exists("LMS Category", name):
		frappe.get_doc({"doctype": "LMS Category", "category": name}).insert()
	return name


def ensure_course(spec, instructor):
	existing = frappe.db.exists("LMS Course", {"title": spec["title"]})
	if existing:
		course = frappe.get_doc("LMS Course", existing)
	else:
		course = frappe.new_doc("LMS Course")
		course.update(
			{
				"title": spec["title"],
				"category": spec["category"],
				"tags": spec["tags"],
				"published": 1,
				"published_on": frappe.utils.now(),
				"instructors": [{"instructor": instructor.name}],
				"short_introduction": spec["intro"],
				"description": spec["description"],
			}
		)
		course.save()

	for chapter_spec in spec["chapters"]:
		chapter_name = frappe.db.exists(
			"Course Chapter", {"course": course.name, "title": chapter_spec["title"]}
		)
		if chapter_name:
			chapter = frappe.get_doc("Course Chapter", chapter_name)
		else:
			chapter = frappe.new_doc("Course Chapter")
			chapter.course = course.name
			chapter.title = chapter_spec["title"]
			chapter.save()
			course.reload()
			course.append("chapters", {"chapter": chapter.name})
			course.save()

		for lesson_title, lesson_content in chapter_spec["lessons"]:
			if frappe.db.exists(
				"Course Lesson",
				{"course": course.name, "chapter": chapter.name, "title": lesson_title},
			):
				continue
			lesson = frappe.new_doc("Course Lesson")
			lesson.course = course.name
			lesson.chapter = chapter.name
			lesson.title = lesson_title
			lesson.content = lesson_content
			lesson.save()
			chapter.reload()
			chapter.append("lessons", {"lesson": lesson.name})
			chapter.save()
	return course


def ensure_question(question, option_1, correct_1, option_2, correct_2):
	existing = frappe.db.exists("LMS Question", {"question": question})
	if existing:
		return frappe.get_doc("LMS Question", existing)
	doc = frappe.new_doc("LMS Question")
	doc.update(
		{
			"question": question,
			"type": "Choices",
			"option_1": option_1,
			"is_correct_1": correct_1,
			"option_2": option_2,
			"is_correct_2": correct_2,
		}
	)
	doc.save()
	return doc


def ensure_quiz():
	title = "Investing Basics Check"
	existing = frappe.db.exists("LMS Quiz", {"title": title})
	if existing:
		return frappe.get_doc("LMS Quiz", existing)
	questions = [
		ensure_question(
			"What force makes long-term investing powerful?",
			"Compounding returns",
			True,
			"Daily trading",
			False,
		),
		ensure_question(
			"What does an index fund hold?",
			"A single company's stock",
			False,
			"A broad basket of many companies",
			True,
		),
		ensure_question(
			"What is the main defense against the risk of any one company failing?",
			"Diversification",
			True,
			"Borrowing to invest more",
			False,
		),
		ensure_question(
			"When does dollar-cost averaging have you invest?",
			"Only when markets fall",
			False,
			"On a fixed schedule regardless of price",
			True,
		),
	]
	quiz = frappe.new_doc("LMS Quiz")
	quiz.update({"title": title, "passing_percentage": 70, "total_marks": 20})
	for question in questions:
		quiz.append("questions", {"question": question.name, "marks": 5})
	quiz.save()
	return quiz


def run():
	# ------------------------------------------------------------ settings

	website = frappe.get_doc("Website Settings")
	website.app_name = "New Money University"
	website.app_logo = "/assets/lms/frontend/learning.svg"
	website.favicon = "/assets/lms/frontend/favicon.png"
	website.home_page = "lms"
	website.disable_signup = 0
	website.save()

	lms_settings = frappe.get_doc("LMS Settings")
	lms_settings.disable_signup = 0
	lms_settings.meta_description = (
		"New Money University: an online school for practical money skills. "
		"Courses on budgeting, investing, and earning online."
	)
	lms_settings.save()

	resend_key = os.environ.get("RESEND_API_KEY")
	if resend_key and not frappe.db.exists("Email Account", {"email_account_name": "Resend Outgoing"}):
		email_account = frappe.new_doc("Email Account")
		email_account.update(
			{
				"email_account_name": "Resend Outgoing",
				"email_id": "university@xsor-email.com",
				"smtp_server": "smtp.resend.com",
				"smtp_port": 587,
				"use_tls": 1,
				"login_id_is_different": 1,
				"login_id": "resend",
				"password": resend_key,
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"enable_incoming": 0,
				"always_use_account_email_id_as_sender": 1,
				"always_use_account_name_as_sender_name": 1,
			}
		)
		email_account.insert()

	# ---------------------------------------------------------------- content

	dean = ensure_user(
		"dean@new-money.42bucks.com", "Dean", "Sterling", ["Moderator", "Course Creator"]
	)
	ensure_category("Finance")
	ensure_category("Business")

	foundations = ensure_course(
		{
			"title": "Money Foundations",
			"category": "Finance",
			"tags": "budgeting, saving, debt",
			"intro": "Take control of your cash flow: budgeting, emergency funds, and a clear plan out of debt.",
			"description": (
				"<p>Most money problems are visibility problems. This course gives you a simple, "
				"repeatable system: see where your money goes, direct it on purpose, build a buffer "
				"that absorbs surprises, and clear debt with a method that sticks.</p>"
				"<p>No jargon, no spreadsheet worship. Every lesson ends with one action you can "
				"complete the same day.</p>"
			),
			"chapters": [
				{
					"title": "Know Your Numbers",
					"lessons": [
						(
							"Where Your Money Actually Goes",
							content(
								para(
									"You cannot direct what you cannot see. The first step is a 30-day picture of "
									"your real spending, not the version you remember."
								),
								head("Fixed vs. variable"),
								para(
									"Fixed costs (rent, subscriptions, insurance) leave on schedule whether you "
									"think about them or not. Variable costs (food, transport, fun) flex with your "
									"attention. Most people overestimate fixed and underestimate variable."
								),
								para(
									"<b>Action:</b> export the last 30 days from your bank, sort every line into "
									"fixed or variable, and total each column. That one number pair explains more "
									"about your finances than any app."
								),
							),
						),
						(
							"Build Your First Budget",
							content(
								para(
									"A budget is not a punishment. It is deciding where money goes before the month "
									"starts, so the month cannot decide for you."
								),
								head("Two frameworks that work"),
								para(
									"<b>50/30/20:</b> 50 percent needs, 30 percent wants, 20 percent saving and debt. "
									"Fast to start, forgiving, good for a first pass."
								),
								para(
									"<b>Zero-based:</b> every unit of income gets a job until nothing is unassigned. "
									"More effort, total clarity. Use it once your 50/30/20 keeps leaking."
								),
								para(
									"<b>Action:</b> run your last month's totals through 50/30/20. Wherever a bucket "
									"is off by more than 10 points, that is next month's single focus."
								),
							),
						),
					],
				},
				{
					"title": "Safety Nets",
					"lessons": [
						(
							"The Emergency Fund",
							content(
								para(
									"An emergency fund is not an investment. It is insurance you sell to yourself: "
									"boring, liquid, and there at 2 a.m. when the car dies."
								),
								head("How much and where"),
								para(
									"Target one month of essential expenses first, then grow it to three to six "
									"months. Keep it in a separate high-yield savings account, one transfer away "
									"but not one tap away."
								),
								para(
									"<b>Action:</b> open a separate savings account today and automate a transfer "
									"for the day after each payday. Size does not matter yet; the pipe does."
								),
							),
						),
						(
							"Getting Out of Debt",
							content(
								para(
									"Debt payoff is a motivation problem wearing a math costume. Pick the method "
									"you will actually finish."
								),
								head("Avalanche vs. snowball"),
								para(
									"<b>Avalanche:</b> pay minimums everywhere, throw every spare unit at the "
									"highest interest rate. Mathematically optimal."
								),
								para(
									"<b>Snowball:</b> attack the smallest balance first for the quick win, then "
									"roll that payment into the next debt. Psychologically optimal."
								),
								para(
									"<b>Action:</b> list every debt with balance, rate, and minimum. Choose one "
									"method, schedule the extra payment, and stop re-deciding every month."
								),
							),
						),
					],
				},
			],
		},
		dean,
	)

	investing = ensure_course(
		{
			"title": "Investing 101",
			"category": "Finance",
			"tags": "investing, index funds, compounding",
			"intro": "From zero to a working portfolio: compounding, risk, index funds, and your first allocation.",
			"description": (
				"<p>Investing is the part of personal finance where doing less usually earns more. "
				"This course covers the handful of ideas that drive almost all long-term results: "
				"compounding, risk and time horizon, diversification through index funds, and a "
				"simple portfolio you can actually maintain.</p>"
				"<p>Nothing here is a recommendation to buy any specific security; it is the "
				"framework to evaluate anything you are offered.</p>"
			),
			"chapters": [
				{
					"title": "Foundations",
					"lessons": [
						(
							"Why Invest at All",
							content(
								para(
									"Cash quietly loses purchasing power to inflation every year. Investing is how "
									"you put money where it grows faster than prices do."
								),
								head("Compounding"),
								para(
									"Returns earn returns. At 7 percent annual growth, money doubles roughly every "
									"ten years; starting ten years earlier can matter more than doubling your "
									"contribution later."
								),
								para(
									"<b>Action:</b> compute how many doubling periods you have before age 65. That "
									"number, not stock picks, is your biggest lever."
								),
							),
						),
						(
							"Risk and Return",
							content(
								para(
									"Risk and return are the same dial viewed from two sides. Anything promising "
									"high return with no risk is mispriced, misunderstood, or a lie."
								),
								head("Your real risk tolerance"),
								para(
									"Volatility only hurts when you must sell during a dip. Money you need within "
									"five years does not belong in stocks; money you will not touch for twenty "
									"years can ride out almost any storm."
								),
								para(
									"<b>Action:</b> split your savings by when you will need them: under 2 years, "
									"2 to 5 years, 5 plus. Only the last bucket is investment money."
								),
							),
						),
					],
				},
				{
					"title": "Putting Money to Work",
					"lessons": [
						(
							"Index Funds and ETFs",
							content(
								para(
									"Picking winning stocks is hard enough that most professionals fail at it after "
									"fees. Index funds sidestep the contest by owning the whole market."
								),
								head("What you get"),
								para(
									"One purchase buys hundreds or thousands of companies, automatic "
									"diversification, and fees near zero. The main differences between providers "
									"are cost and which index they track."
								),
								para(
									"<b>Action:</b> look up the expense ratio of any fund you are considering. "
									"Above 0.5 percent, demand a very good reason."
								),
							),
						),
						(
							"Your First Portfolio",
							content(
								para(
									"A portfolio you understand and keep is worth more than a clever one you "
									"abandon. Start with two or three broad funds and a rule for adding money."
								),
								head("Dollar-cost averaging"),
								para(
									"Invest a fixed amount on a fixed schedule. You automatically buy more when "
									"prices are low, less when they are high, and you never have to guess the "
									"bottom."
								),
								para(
									"<b>Action:</b> set up an automatic monthly transfer to your brokerage, even a "
									"small one. Consistency builds the habit the returns will ride on."
								),
							),
						),
					],
				},
			],
		},
		dean,
	)

	earning = ensure_course(
		{
			"title": "Earning Online",
			"category": "Business",
			"tags": "freelancing, side income, clients",
			"intro": "Turn a skill into income: pick your lane, land a first client, and price your work properly.",
			"description": (
				"<p>The internet pays for solved problems. This course walks the shortest path from "
				"a skill you already have to money in your account: choosing between services and "
				"products, finding the first paying client, and pricing so the work is worth "
				"doing.</p>"
				"<p>It is deliberately small. One finished client project teaches more than fifty "
				"hours of research, and every lesson pushes you toward that first finish line.</p>"
			),
			"chapters": [
				{
					"title": "Pick Your Lane",
					"lessons": [
						(
							"Freelancing vs. Products",
							content(
								para(
									"Services trade time for money and pay immediately. Products trade upfront work "
									"for scalable income and pay slowly, then suddenly."
								),
								head("Start with services"),
								para(
									"Freelancing gives you revenue this month, direct customer contact, and a "
									"catalog of real problems. The best products are usually built later, from "
									"patterns your clients keep paying you to solve."
								),
								para(
									"<b>Action:</b> write one sentence: 'I help X do Y.' If you cannot fill it in, "
									"the next lesson is for you."
								),
							),
						),
						(
							"Choosing a Skill That Pays",
							content(
								para(
									"You do not need a rare skill; you need a skill attached to a business outcome "
									"someone already budgets for."
								),
								head("The outcome test"),
								para(
									"Writing becomes 'landing pages that convert.' Spreadsheets become 'monthly "
									"reporting a founder stops doing personally.' The closer your skill sits to "
									"revenue or saved time, the easier the sale."
								),
								para(
									"<b>Action:</b> list three things people have thanked you for at work. Rewrite "
									"each as a business outcome with a number in it."
								),
							),
						),
					],
				},
				{
					"title": "First Dollars",
					"lessons": [
						(
							"Landing Your First Client",
							content(
								para(
									"Your first client almost never comes from a cold platform. They come from "
									"someone who already trusts you, given a specific, easy yes."
								),
								head("The specific offer"),
								para(
									"'Let me know if you need help' produces nothing. 'I will rewrite your pricing "
									"page this week for a fixed fee; if you do not like it, you pay nothing' "
									"produces conversations."
								),
								para(
									"<b>Action:</b> send that shaped offer to five people who know your work. "
									"Aim for replies, not clients; the first client falls out of the replies."
								),
							),
						),
						(
							"Pricing Your Work",
							content(
								para(
									"Price is a statement about the outcome, not your hourly discomfort. Charge by "
									"the project, anchored to what the result is worth."
								),
								head("A floor and a rule"),
								para(
									"Set a personal minimum below which work is not worth switching contexts for. "
									"Then raise prices every third project until two out of ten prospects say no; "
									"before that point you are underpriced."
								),
								para(
									"<b>Action:</b> price your last favor as a project. That number, plus 30 "
									"percent, is your opening quote for the next one."
								),
							),
						),
					],
				},
			],
		},
		dean,
	)

	quiz = ensure_quiz()
	quiz_chapter_name = frappe.db.exists(
		"Course Chapter", {"course": investing.name, "title": "Putting Money to Work"}
	)
	if quiz_chapter_name and not frappe.db.exists(
		"Course Lesson", {"course": investing.name, "title": "Check Your Understanding"}
	):
		quiz_chapter = frappe.get_doc("Course Chapter", quiz_chapter_name)
		lesson = frappe.new_doc("Course Lesson")
		lesson.course = investing.name
		lesson.chapter = quiz_chapter.name
		lesson.title = "Check Your Understanding"
		lesson.content = content(
			para("A short check on the core ideas from this course. Passing score is 70 percent."),
			block("quiz", quiz=quiz.name),
		)
		lesson.save()
		quiz_chapter.reload()
		quiz_chapter.append("lessons", {"lesson": lesson.name})
		quiz_chapter.save()

	frappe.db.commit()

	print("Seeded:")
	print("  courses:", frappe.db.count("LMS Course", {"published": 1}))
	print("  chapters:", frappe.db.count("Course Chapter"))
	print("  lessons:", frappe.db.count("Course Lesson"))
	print("  quiz:", quiz.name)
	print("  outgoing email configured:", bool(frappe.db.exists("Email Account", {"email_account_name": "Resend Outgoing"})))
