# util for in this file
def add_if_relevant(formdata, key, targetkey, target, bools):
    if key in formdata:
        if ('param_' in key and formdata[key] == 'on') or targetkey in bools:
            target[targetkey] = True
        elif formdata[key]:
            target[targetkey] = formdata[key]

# used in creating (& editing) models
def raw_to_config(formdata, bools):
    model = {}

    # tab: general
    general = {}
    general['output-mode'] = formdata.get('output_mode_field')
    general['mode'] = formdata.get('model_mode_field')
    if general['mode'] == "Single":
        pass # nothing else here really
    else: # Ensemble
        general['combination-strategy'] = formdata.get('combination_strategy_field')
    model['general'] = general

    # if single:
    if general['mode'] == "Single":
        # tab: pre-processing
        prepro = {}
        prepro['input-mode'] = formdata.get('input_mode_field')
        # get all params
        input_params = [x for x in formdata if x.startswith('param_')]
        params = {}
        for p in input_params:
            add_if_relevant(formdata, p, p[6:], params, bools)
        prepro['params'] = params

        model['pre-processing'] = prepro

        # tab: classifier
        classifier = {}
        classifier['classifier'] = formdata.get('classifier_field')
        hyper_params = [x for x in formdata if x.startswith('hparam_')]
        hparams = {}
        for p in hyper_params:
            add_if_relevant(formdata, p, p[7:], hparams, bools)
        classifier['hyper-params'] = hparams
        model['classifier'] = classifier
    else: # ensemble
        # tab: ensemble classifiers
        ens_class = []
        ens_classifiers_count = int(formdata.get('ensemble_classifier_count_field', 0))
        
        for i in range(ens_classifiers_count):
            hparam_prefix = f'ens{i}_hparam_'
            hyper_params = [x for x in formdata if x.startswith(hparam_prefix)]
            hparams = {}
            for p in hyper_params:
                add_if_relevant(formdata, p, p[len(hparam_prefix):], hparams, bools)

            param_prefix = f'ens{i}_param_'
            input_params = [x for x in formdata if x.startswith(param_prefix)]
            params = {}
            for p in input_params:
                add_if_relevant(formdata, p, p[len(param_prefix):], params, bools)

            ens_class.append({
                'classifier': formdata.get(f'ens_class_{i}_select'),
                'hyper-params': hparams, 
                'input-mode': formdata.get(f'ens_input_{i}_select'),
                'params': params
            })
        model['ensemble classifiers'] = ens_class

        if general['combination-strategy'] == 'stacking':
            # tab: ensemble meta classifier
            meta_class = {}
            meta_class['classifier'] = formdata.get('stacking_meta_classifier_field')
            prefix = 'stacker_hparam_'
            hyper_params = [x for x in formdata if x.startswith(prefix)]
            hparams = {}
            for p in hyper_params:
                add_if_relevant(formdata, p, p[len(prefix):], hparams, bools)
            meta_class['hyper-params'] = hparams

            model['ensemble meta classifier'] = meta_class

    # tab: training
    training = {}
    training['epochs'] = formdata.get('epochs_field')
    add_if_relevant(formdata, 'split_size_field', 'split-size', training, bools)
    add_if_relevant(formdata, 'max_train_field', 'max-train', training, bools)
    add_if_relevant(formdata, 'architectural_only_field', 'architectural-only', training, bools)
    add_if_relevant(formdata, 'project_mode_field', 'project-mode', training, bools)
    if 'project-mode' in training and training['project-mode'].lower() == 'test-project':
        training['test-project'] = formdata['test_project_field']
    add_if_relevant(formdata, 'class_balancer_field', 'class-balancer', training, bools)
    add_if_relevant(formdata, 'apply_ontology_classes_field', 'apply-ontology-classes', training, bools)
    add_if_relevant(formdata, 'batch_size_field', 'batch-size', training, bools)
    if 'use_early_stopping_field' in formdata:
        training['use-early-stopping'] = True
        add_if_relevant(formdata, 'early_stopping_patience_field', 'early-stopping-patience', training, bools)
        add_if_relevant(formdata, 'early_stopping_min_delta_field', 'early-stopping-min-delta', training, bools)
        add_if_relevant(formdata, 'early_stopping_attribute_field', 'early-stopping-attribute', training, bools)

    model['training'] = training

    return model

# helper for below fn
def _config_to_cli_hparams(hparams, prefix=''):
    command = ''
    hyper_param_keys = [x for x in hparams if not 'optimizer' in x]
    for hparam in hyper_param_keys:
        command += f" {prefix}{hparam}={hparams[hparam]}"
    if 'optimizer' in hparams:
        if hparams['optimizer'] == 'sgd':
            command += f" {prefix}optimizer=sgd_{hparams['optimizer_sgdvalue']}"
        else:
            command += f" {prefix}optimizer={hparams['optimizer']}"

    return command

# helper for below fn
def _config_to_cli_params(params, prefix=''):
    command = ''
    for param in params:
        if param == 'stemming_lemma':
            match params[param]:
                case 'Stemming':
                    command += ' use-stemming=true'
                    break
                case 'Lemmatization':
                    command += ' use-lemmatization=true'
        else:
            command += f' {prefix}{param}={params[param]}'

    return command

# used in training models
def config_to_cli(model_config, target_model_path):
    command = "__main__.py run"

    if model_config['general']['mode'] == "Single":
        # classifier
        command += " " + model_config['classifier']['classifier']

        # hyper-parameters
        hparams = model_config['classifier']['hyper-params']
        if len(hparams) > 0:
            command += ' --hyper-params'
            command += _config_to_cli_hparams(hparams)

        # pre-processor parameters
        command += ' --input-mode ' + model_config['pre-processing']['input-mode']
        params = model_config['pre-processing']['params']
        if len(params) > 0:
            command += ' --params'
            command += _config_to_cli_params(params)

    else:
        # setup
        classifiers = []
        hparams = {}
        input_modes = []
        params = {}
        for c in model_config['ensemble classifiers']:
            classifiers.append(c['classifier'])
            if not c['classifier'] in hparams:
                hparams[c['classifier']] = []
            hparams[c['classifier']].append(c['hyper-params'])
            input_modes.append(c['input-mode'])
            if not c['input-mode'] in params:
                params[c['input-mode']] = []
            params[c['input-mode']].append(c['params'])

        # classifiers
        command += ' ' + ' '.join(classifiers)
        
        # hparams
        hyper_params_part = ' --hyper-params'
        hyper_params_count = 0
        for classifier_set in hparams:
            for i in range(len(hparams[classifier_set])):
                this_hparams = hparams[classifier_set][i]
                hyper_params_part += _config_to_cli_hparams(this_hparams, f'{classifier_set}[{i}].')
                hyper_params_count += len(this_hparams)
        if hyper_params_count > 0:
            command += hyper_params_part
        
        # input modes
        command += ' --input-mode '
        command += ' '.join(input_modes)

        # params
        params_part = ' --params'
        params_count = 0
        for input_mode_set in params:
            for i in range(len(params[input_mode_set])):
                this_params = params[input_mode_set][i]
                params_part += _config_to_cli_params(this_params, f'{input_mode_set}[{i}].')
                params_count += len(this_params)
        if params_count > 0:
            command += params_part
        
        # combination strategy
        strat = model_config['general']['combination-strategy']
        if strat in ["stacking","voting"]: # ensemble-strategy
            command += f' --ensemble-strategy {strat}'
        else:
            command += f' --combination-strategy {strat}'

        # stacker if applicable
        if strat == 'stacking':
            command += ' --stacking-meta-classifier '
            command += model_config['ensemble meta classifier']['classifier']
            command += ' --stacking-meta-classifier-hyper-parameters'
            command += _config_to_cli_hparams(model_config['ensemble meta classifier']['hyper-params'])

            # todo change if we ever get more stackers available than just fullyconnectedmodel
            command += ' --stacking-no-matrix'
            # never --use-concat!

    # output mode
    command += " --output-mode " + model_config['general']['output-mode']

    # training
    for param in model_config['training']:
        command += f" --{param}"
        if type(model_config['training'][param]) != bool:
            command += f" {model_config['training'][param]}"

    # finalize with some always-set parameters
    additional_params = {
        "file": "app/data/training.json",
        "force-regenerate-data": True,
        "store-model": True,
        "target-model-path": target_model_path
    }
    if 'apply-ontology-classes' in model_config['training']:
        additional_params['ontology-classes'] = 'app/data/ontologies.json'

    args = command.split(' ')
    for param in additional_params:
        args.append(f'--{param}')
        if type(additional_params[param]) != bool:
            args.append(str(additional_params[param]))

    print(' '.join(args)) # print whole command easy to read & check

    return args

# to be used in edit model. convert a config to default values for the form
def config_to_raw():
    # todo
    return {}