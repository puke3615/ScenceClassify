from keras.applications.xception import *
from keras.optimizers import *
from keras.callbacks import *
from keras.models import *
from keras.layers import *
from tensorboard import *
from generator import *
from config import *

import im_utils
import utils
import os


class BaseClassifier(object):
    def __init__(self, name, im_size, lr=2e-3, batch_size=BATCH_SIZE, weights_mode='acc', optimizer=None):
        # receive params
        self.name = name
        self.im_size = im_size
        self.lr = lr
        self.batch_size = batch_size
        self.weights_mode = weights_mode
        self.optimizer = optimizer

        # parse context
        self.context = CONTEXT(self.name)
        self.path_summary = self.context['summary']
        self.path_weights = self.context['weights']

        # build model
        self.model = self.build_model()
        self._compiled = False

    def image_generator(self, train=True):
        def wrap(value):
            return float(train) and value

        return ImageDataGenerator(
            channel_shift_range=wrap(25.5),
            rotation_range=wrap(15.),
            width_shift_range=wrap(0.2),
            height_shift_range=wrap(0.2),
            shear_range=wrap(0.2),
            zoom_range=wrap(0.2),
            horizontal_flip=train,
            preprocessing_function=im_utils.default_preprocess_input,
        )

    def data_generator(self, path_image, train=True):
        return self.image_generator(train).flow_from_directory(
            path_image,
            classes=['%02d' % i for i in range(CLASSES)],
            target_size=(self.im_size, self.im_size),
            batch_size=self.batch_size,
            class_mode='categorical',
            crop_mode='random' if train else 'center',
        )

    def build_model(self, weights_mode='acc'):
        if weights_mode not in [None, 'acc', 'loss']:
            raise Exception('Weights set error.')
        if weights_mode:
            weights = utils.get_best_weights(os.path.dirname(self.path_weights), weights_mode)
        else:
            weights = None

        load_imagenet_weights = self.context['load_imagenet_weights']
        model_xception = Xception(include_top=False,
                                  weights='imagenet' if not weights and load_imagenet_weights else None,
                                  input_shape=(self.im_size, self.im_size, 3), pooling='avg')
        for layer in model_xception.layers:
            layer.trainable = False
        x = model_xception.output
        x = Dense(CLASSES, activation='softmax')(x)
        model = Model(inputs=model_xception.inputs, outputs=x)

        if weights:
            model.load_weights(weights, True)
            print('Load %s successfully.' % weights)
        else:
            print('Model params not found.')
        return model

    def compile_mode(self, force=False):
        if not self._compiled or force:
            self._compiled = True
            if not self.optimizer:
                self.optimizer = Nadam(self.lr)
            self.model.compile(loss='categorical_crossentropy', optimizer=self.optimizer, metrics=['accuracy'])

    def train(self):
        # calculate files number
        file_num = utils.calculate_file_num(PATH_TRAIN_IMAGES)
        steps_train = file_num // self.batch_size
        print('Steps number is %d every epoch.' % steps_train)
        steps_val = utils.calculate_file_num(PATH_VAL_IMAGES) // self.batch_size

        # build data generator
        train_generator = self.data_generator(PATH_TRAIN_IMAGES)
        val_generator = self.data_generator(PATH_VAL_IMAGES, train=False)

        # compile model if not
        self.compile_mode()

        # start training
        utils.ensure_dir(os.path.dirname(self.path_weights))
        try:
            self.model.fit_generator(
                train_generator,
                steps_per_epoch=steps_train,
                callbacks=[
                    ModelCheckpoint(self.path_weights, verbose=1),
                    StepTensorBoard(self.path_summary, skip_steps=200)
                ],
                epochs=EPOCH,
                validation_data=val_generator,
                validation_steps=steps_val,
                verbose=1,
            )
        except KeyboardInterrupt:
            print('\nStop by keyboardInterrupt, try saving weights.')
            # model.save_weights(PATH_WEIGHTS)
            print('Save weights successfully.')


if __name__ == '__main__':
    classifier = BaseClassifier('base', IM_SIZE_299, lr=2e-4)
    classifier.train()
