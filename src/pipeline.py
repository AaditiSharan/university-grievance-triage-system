# Single entry point. 
# Runs preprocess → rules → classifier → incident match → priority → route → save → audit, and returns one result object. 
# Everything else calls this.