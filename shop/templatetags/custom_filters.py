from django import template

register = template.Library()

@register.filter(name='currency')
def currency(value):
    try:
        val = float(value)
    except (ValueError, TypeError):
        return value
    
    is_negative = val < 0
    val = abs(val)
    
    s = "{:.2f}".format(val)
    parts = s.split('.')
    integer_part = parts[0]
    decimal_part = parts[1]
    
    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        other = integer_part[:-3]
        
        # Loop to add commas every 2 digits from right to left
        formatted_other = ''
        while len(other) > 0:
            # Take last 2
            chunk = other[-2:]
            other = other[:-2]
            if formatted_other:
                formatted_other = chunk + ',' + formatted_other
            else:
                formatted_other = chunk
        
        res = formatted_other + ',' + last3
    else:
        res = integer_part
        
    final_res = f"₹{res}.{decimal_part}"
    if is_negative:
        final_res = "-" + final_res
    return final_res

@register.filter(name='subtract')
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value
