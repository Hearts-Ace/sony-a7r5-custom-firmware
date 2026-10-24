"""New tasks default to the pinned R5 capture; saved responses stay explicit."""
def default_response():
    from measured_response import default_response as r5_response
    return r5_response()
