import argparse

def main():
    # Create the main parser
    
    parser = argparse.ArgumentParser(description='''Data Pipelines Operations
                                                    use flag --mode with a choice of following method
                                                    reload: delete existing data in the db and reload them to the latest
                                                    update: check the latest data in api and update new data''')

    parser.add_argument('--mode', choices=['reload', 'update'], help='''reload: delete existing data in the db and reload them to the latest
                                                                        update: check the latest data in api and update new data''')
    


    # Parse the command-line arguments
    args = parser.parse_args()

    # Process the selected operation
    mode = args.mode
    if mode:
        print(f'Selected mode: {mode}')
        if mode == 'update':
            print('update operation in coming')
        elif mode == 'reload':
            print('reload operation in coming')
    else:
        print('please select')
if __name__ == '__main__':
    main()