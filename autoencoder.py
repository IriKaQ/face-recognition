#!/usr/bin/env python3
# coding: utf-8

'''
Auto Encoder Neural Networks
'''

__author__ = 'IriKa'

import tensorflow as tf
import tools

class stack_autoencoder:
    '''A NN AutoEncoder.
    '''
    def __init__(self, in_data, layer_num, hidden_outputs):
        '''Constructor

        Args:
            in_data: A 4-D `Tensor`. Note, the last 3-D shape must be known and cannot be `None`.
            layer_num: A `int`. Indicates the number of layers of the `stack_autoencoder`.
            hidden_outputs: A list of hidden layers output feature maps.

        Raises:
            ValueError: If the length of the `hidden_outputs` is not equal `layer_num`.
        '''
        shape = in_data.shape
        if None in shape[-3:]:
            raise ValueError('The last 3-D shape must be known and cannot be None.')
        if len(hidden_outputs) != layer_num:
            raise ValueError('The length of the hidden_outputs must be equal layer_num.')

        self.scope_name = 'stack_autoencoder'
        self.in_data = in_data
        self.in_shape = self.in_data.shape
        self.layer_num = layer_num
        # The first element is the channels of input layer.
        self.hidden_outputs = self.in_shape[-1:] + hidden_outputs

    def codec(imgs, filter, is_encode,
              stddev=5e-2,
              name=None,
              new_size=None,
              ksize=[1, 2, 2, 1],
              strides=[1, 2, 2, 1]):
        '''Single layer encoder and decoder.

        Args:
            imgs: Images for encode or decode.
            filter: The convolution kernel shape.
            is_encode: `True` indicates that it is an encoder, and `False` indicates that it is a decoder.
            stddev: The convolution kernel initializes the standard deviation.
            name: Name of the codec. Default `encoder` if `is_encode` is `True`, else is `decoder`.
            new_size: The size of the decoder output. If `is_encode` is `False`, the value must be set.
            ksize: Downsampling ksize.
            strides: Downsampling strides.

        Returns:
            Codec output.

        Raises:
            ValueError: If `is_encode` is not `bool`.
                And if `new_size` is `None` when `is_encode` is `False`.
        '''
        if not isinstance(is_encode, bool):
            raise ValueError('The value of the is_encode must be a bool type.')

        if name is None:
            if is_encode:
                name = 'encoder'
            else:
                name = 'decoder'

        layers = [imgs]

        with tf.variable_scope(name) as scope:
            if not is_encode:
                # Upsampling.
                if new_size is None:
                    raise ValueError('The value of the new_size must be set if the is_encode is False.')
                unsampling = tf.image.resize_nearest_nerghbor(layers[-1], new_size, name='upsample')
                layers.append(unsampling)

            # Convolution.
            kernel = tools.variable_with_weight_decay('weights',
                                                      shape=filter,
                                                      stddev=stddev,
                                                      wd=None)
            conv = tf.nn.conv2d(layers[-1], kernel, [1, 1, 1, 1], padding='SAME')
            biases = tools.variable_on_cpu('biased', filter[-1:], tf.constant_initializer(0.0))
            pre_activation = tf.nn.bias_add(conv, biases)
            # Activation.
            activation = tf.nn.relu(pre_activation, name=scope.name)
            layers.append(activation)

            tools.activation_summary(layers[-1])

            if is_encode:
                # Downsampling.
                downsampling = tf.nn.max_pool(layers[-1], ksize=ksize,
                                         strides=strides, padding='SAME', name='downsample')
                layers.append(downsampling)
        return layers[-1]

    def gen_model(self, filter_sizes=[3, 3]):
        '''A wrapper that generates the model function.

        Args:
            filter_sizes:   The sizes of the convolution kernel. The default if `[3, 3]`, but you can also customiz it.
                You can only provide one size so that all convolution kernel use the same size.
                Well, you can provide size for each layer of convolution kernel.
                *NOTE*: The convolution kernel of the encoder and decoder of the corresponding layer will use the same size.

        Returns:
            The final decoder output.
            Well, the output of the hidden layer will also be stored.
        '''
        with tf.variable_scope(self.scope_name) as scope:
            return self.__gen_model(filter_sizes)

    def __gen_model(self, filter_sizes):
        '''A generates the model function.

        Args:
            filter_sizes:   The sizes of the convolution kernel.
                See the `stack_autoencoder.gen_model` for more information.

        Returns:
            The final decoder output.
            Well, the output of the hidden layer will also be stored.
        '''
        if len(filter_sizes) != 1 or len(filter_sizes) != self.layer_num:
            raise ValueError('The length of filter_sizes must be equal 1 or layer_num.')
        self.layer_train_ph = tf.placeholder(name='layer_train', shape=(), dtype=tf.uint8)
        zero_constant = tf.constant(0.0, dtype=tf.float32, shape=(), name='zero_constant')
        if len(filter_sizes) == 1:
            filter_sizes = filter_sizes * self.layer_num
        size_each_hidden = [self.in_shape[-3:-1]]
        layers = [self.in_data]

        # All of the encode outputs will store here.
        self.encoded = [self.in_data]

        # Encode
        with tf.variable_scope('encoder') as scope:
            for i in range(self.layer_num):
                name = 'hidden_%d' % i+1
                filter = filter_sizes[i] + layers[-1].shape[-1:] + [self.hidden_outputs[i+1]]
                layer = layers[-1]
                if i != 0:
                    include_fn = lambda var=layers[-1]: var
                    exclude_fn = lambda: zero_constant
                    layer = tf.cond(tf.less(i, self.layer_train_ph), include_fn, exclude_fn)
                hidden = codec(layer, filter, True, name=name)
                size_each_hidden.append(hidden.shape[-3:-1])
                layers.append(hidden)
                self.encoded.append(hidden)

        # Decode
        with tf.variable_scope('decoder') as scope:
            for i in range(self.layer_num-1, -1, -1):
                name = 'hidden_%d' % i+1
                filter = filter_sizes[i] + layers[-1].shape[-1:] + [self.hidden_outputs[i]]
                layer = layers[-1]
                if i != 0:
                    include_fn = lambda var=layers[-1]: var
                    exclude_fn = lambda: layers[i]
                    layer = tf.cond(tf.less(i, self.layer_train_ph), include_fn, exclude_fn)
                hidden = codec(layer, filter, False, name=name, new_size=size_each_hidden[i])
                layers.append(hidden)

        # the net output - decoded.
        self.decoded = layers[-1]
        return self.decoded

    def get_ph(self):
        ''' Get placeholder of the Stack AutoEncoder.
        '''
        return self.layer_train_ph

    def get_encoded(self, index=None):
        ''' Get encoded output of the AutoEncoder.

        The hidden layer coded output can be used to make sparse penalties during network training.
        Or visualize.

        Args:
            index:  A `int`. The default is equal to `layer_num`. `0` means to get input of the AutoEncoder.
                The value must be less than `layer_num`.

        Raises:
            ValueError: If `index` is greater than `layer_num`.
        '''
        if index > self.layer_num:
            raise ValueError('The index must be less than the layer_num.')

        if index is None:
            index = self.layer_num
        return self.encoded[index]

    def get_decoded(self):
        ''' Get decoded output of the Stack AutoEncoder.
        '''
        return self.decoded

    def get_variable_for_layer(self, index, trainable=None):
        ''' Get variable of the Stack AutoEncoder.

        Get the variables of the specified layer, which is convenient for Stack AutoEncoder training.

        Args:
            index:      A `int`. Specifies which layer of variables to retrieve,
                including the corresponding encoder layer and decoder layer.
            trainable:  A `bool`. Indicates whether it is a trainingable variable. The `True` and default are trainable.
        '''
        var_list = []
        hidden_name = 'encoder/hidden_%d' % index, 'decoder/hidden_%d' % index
        if trainable is True or trainable is None:
            all_vars = tf.trainable_variables(scope=self.scope_name)
        else:
            all_vars = tf.global_variables(scope=self.scope_name)
        for var in all_vars:
            if (hidden_name[0] in var.name) or (hidden_name[1] in var.name):
                var_list.append(var)
        return var_list

def main():
    pass

if __name__ == "__main__":
    import numpy as np
    from casia_webface import casia_webface
    from preprocessing import preprocessing_for_image
    # For display
    from matplotlib import pyplot as plt
    main()

