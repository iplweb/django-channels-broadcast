from django import template
from django.contrib.messages import constants
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter(name="message_level_to_css_class")
@stringfilter
def message_level_to_css_class(value):
    return constants.DEFAULT_TAGS.get(int(value))
