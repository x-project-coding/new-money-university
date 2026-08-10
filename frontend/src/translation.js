import { createResource } from 'frappe-ui'

// Resolved once the translation dictionary is installed (or immediately if it
// already is). main.js awaits this before mounting: `__` is not reactive, so
// anything rendered before the dictionary arrives stays untranslated forever
// (the sidebar was permanently English on non-English sites).
let markTranslationsReady
export const translationsReady = new Promise((resolve) => {
	markTranslationsReady = resolve
})

export default function translationPlugin(app) {
	app.config.globalProperties.__ = translate
	window.__ = translate
	if (!window.translatedMessages) {
		fetchTranslations()
	} else {
		markTranslationsReady()
	}
}

function translate(message) {
	let translatedMessages = window.translatedMessages || {}
	let translatedMessage = translatedMessages[message] || message

	const hasPlaceholders = /{\d+}/.test(message)
	if (!hasPlaceholders) {
		return translatedMessage
	}
	return {
		format: function (...args) {
			return translatedMessage.replace(
				/{(\d+)}/g,
				function (match, number) {
					return typeof args[number] != 'undefined'
						? args[number]
						: match
				}
			)
		},
	}
}

function fetchTranslations(lang) {
	createResource({
		url: 'lms.lms.api.get_translations',
		cache: 'translations',
		auto: true,
		transform: (data) => {
			window.translatedMessages = data
			markTranslationsReady()
		},
		onError: () => {
			// Never block app boot on a failed translation fetch.
			markTranslationsReady()
		},
	})
}
