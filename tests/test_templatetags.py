from django.template import Context, Template


def test_message_level_to_css_class_renders():
    tmpl = Template(
        "{% load notifications %}{{ level|message_level_to_css_class }}"
    )
    assert tmpl.render(Context({"level": "25"})) == "success"
    assert tmpl.render(Context({"level": "40"})) == "error"
