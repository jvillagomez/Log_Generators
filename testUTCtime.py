import datetime

if __name__ == '__main__':
    _time = datetime.datetime.utcnow()
    hhmmss = _time.strftime('%H:%M')
    print(_time)
    print(hhmmss)
